"""Institution-reviewed scholarship awards; no external cash disbursements."""
from decimal import Decimal
from django.conf import settings
from django.db import models,transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator,MaxValueValidator
from django.utils import timezone
from .models import Program,Term
from .registrar import StudentProfile
from .services import FinalGrade,LedgerEntry
from .operations import FinancialAidAward,AuditEvent
from .notification_models import notify


class ScholarshipFund(models.Model):
    code=models.CharField(max_length=40)
    name=models.CharField(max_length=150)
    term=models.ForeignKey(Term,on_delete=models.PROTECT)
    program=models.ForeignKey(Program,on_delete=models.PROTECT,null=True,blank=True)
    description=models.TextField(max_length=4000)
    budget=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    maximum_award=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    minimum_gpa=models.DecimalField(max_digits=3,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0),MaxValueValidator(4)])
    minimum_credits=models.PositiveSmallIntegerField(default=0)
    opens=models.DateTimeField()
    closes=models.DateTimeField()
    published=models.BooleanField(default=False)
    approval_reference=models.CharField(max_length=200,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["code","term"],name="unique_scholarship_fund_term")]
    def __str__(self): return f"{self.name} / {self.term}"
    @property
    def committed(self):
        return self.awards.filter(status__in=["approved","disbursed"]).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    def clean(self):
        if self.opens and self.closes and self.opens>=self.closes: raise ValidationError("Applications must close after opening.")
        if self.published and not self.approval_reference.strip(): raise ValidationError("Publish only after institutional policy approval.")
        if self.budget is not None and self.maximum_award is not None and self.maximum_award>self.budget: raise ValidationError("Maximum award exceeds the fund budget.")
        if self.pk and self.budget is not None and self.budget<self.committed: raise ValidationError("Budget cannot be less than committed awards.")
    @transaction.atomic
    def save(self,*args,**kwargs):
        if self.pk: type(self).objects.select_for_update().get(pk=self.pk)
        self.full_clean();super().save(*args,**kwargs)


class ScholarshipApplication(models.Model):
    fund=models.ForeignKey(ScholarshipFund,on_delete=models.PROTECT,related_name="applications")
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    requested_amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    statement=models.TextField(max_length=4000)
    renewal_of=models.ForeignKey("ScholarshipAward",on_delete=models.PROTECT,null=True,blank=True,related_name="renewal_applications")
    eligibility_snapshot=models.JSONField()
    status=models.CharField(max_length=12,default="pending",choices=[("pending","Pending"),("approved","Approved"),("declined","Declined"),("withdrawn","Withdrawn")])
    submitted=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["fund","student"],name="one_scholarship_application")]


class ScholarshipAward(models.Model):
    application=models.OneToOneField(ScholarshipApplication,on_delete=models.PROTECT,related_name="award")
    fund=models.ForeignKey(ScholarshipFund,on_delete=models.PROTECT,related_name="awards")
    aid=models.OneToOneField(FinancialAidAward,on_delete=models.PROTECT,related_name="scholarship_award")
    amount=models.DecimalField(max_digits=12,decimal_places=2)
    status=models.CharField(max_length=12,default="approved",choices=[("approved","Approved"),("disbursed","Posted to account"),("cancelled","Cancelled"),("revoked","Reversed")])
    approval_snapshot=models.JSONField()
    credit=models.OneToOneField(LedgerEntry,on_delete=models.PROTECT,null=True,blank=True,related_name="scholarship_credit")
    reversal=models.OneToOneField(LedgerEntry,on_delete=models.PROTECT,null=True,blank=True,related_name="scholarship_reversal")


class ScholarshipEvent(models.Model):
    application=models.ForeignKey(ScholarshipApplication,on_delete=models.PROTECT,related_name="events")
    action=models.CharField(max_length=30)
    reason=models.TextField(max_length=2000)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)


def eligibility(student,fund):
    grades=list(FinalGrade.objects.filter(student=student,released=True,course__term__ends__lte=timezone.localdate()).select_related("course"))
    graded=[g for g in grades if g.quality_points is not None]
    attempted=sum(g.course.credits for g in graded)
    gpa=sum((g.quality_points*g.course.credits for g in graded),Decimal(0))/attempted if attempted else None
    earned=sum(g.credits_earned for g in grades)
    reasons=[]
    if student.status!="active" or not student.user.is_active: reasons.append("An active student account is required.")
    if fund.program_id and student.program_id!=fund.program_id: reasons.append("This fund is restricted to another program.")
    if fund.minimum_gpa is not None and (gpa is None or gpa<fund.minimum_gpa): reasons.append("The minimum GPA is not met by released completed-term grades.")
    if earned<fund.minimum_credits: reasons.append("The minimum earned credits are not met.")
    return {"eligible":not reasons,"reasons":reasons,"gpa":str(gpa.quantize(Decimal("0.01"))) if gpa is not None else None,"earned_credits":earned,"minimum_gpa":str(fund.minimum_gpa) if fund.minimum_gpa is not None else None,"minimum_credits":fund.minimum_credits,"program_id":fund.program_id,"approval_reference":fund.approval_reference,"evaluated":timezone.now().isoformat()}


def event(application,action,reason,actor):
    entry=ScholarshipEvent.objects.create(application=application,action=action,reason=reason,actor=actor)
    AuditEvent.objects.create(actor=actor,action="scholarship_"+action,target=str(application.pk))
    notify(application.student.user,"financial_aid","Scholarship update","Your scholarship application has an update. View Scholarships for the decision and history.",f"scholarship:{entry.pk}")


@transaction.atomic
def submit_application(student,fund,amount,statement,renewal=None):
    # All award operations use fund -> student -> application locks.
    fund=ScholarshipFund.objects.select_for_update().get(pk=fund.pk)
    student=StudentProfile.objects.select_for_update().get(pk=student.pk)
    if not fund.published or not fund.opens<=timezone.now()<fund.closes: raise ValidationError("Applications are not open.")
    if ScholarshipApplication.objects.filter(fund=fund,student=student).exists(): raise ValidationError("An application is already recorded for this fund and term.")
    snapshot=eligibility(student,fund)
    if not snapshot["eligible"]: raise ValidationError(snapshot["reasons"])
    amount=Decimal(amount)
    if not amount.is_finite() or amount<=0 or amount>fund.maximum_award or amount!=amount.quantize(Decimal("0.01")): raise ValidationError("Requested amount exceeds the fund limit or is invalid.")
    if renewal:
        renewal=ScholarshipAward.objects.select_related("application","fund__term").get(pk=renewal.pk)
        if renewal.application.student_id!=student.pk or renewal.status!="disbursed" or renewal.fund.code!=fund.code or renewal.fund.term.ends>=fund.term.starts: raise ValidationError("Renewal requires your posted award from an earlier term of this fund.")
    item=ScholarshipApplication(fund=fund,student=student,requested_amount=amount,statement=statement,renewal_of=renewal,eligibility_snapshot=snapshot)
    item.full_clean();item.save();event(item,"submitted","Application submitted",student.user)
    return item


def lock_application(application):
    fund=ScholarshipFund.objects.select_for_update().get(pk=application.fund_id)
    student=StudentProfile.objects.select_for_update().get(pk=application.student_id)
    item=ScholarshipApplication.objects.select_for_update().get(pk=application.pk)
    return fund,student,item


@transaction.atomic
def decide_application(application,outcome,reason,actor,amount=None):
    fund,student,item=lock_application(application)
    if outcome not in {"approved","declined","withdrawn"} or not reason.strip(): raise ValidationError("A decision and reason are required.")
    if item.status!="pending":
        if outcome=="approved" and item.status=="approved" and item.award.amount!=Decimal(amount or 0): raise ValidationError("This application was already approved for a different amount.")
        if item.status!=outcome: raise ValidationError("The application already has a different decision.")
        return item
    if outcome=="approved":
        if actor.pk==student.user_id: raise ValidationError("Another authorized officer must approve your application.")
        fund.full_clean()
        if not fund.published: raise ValidationError("The approved fund must remain published for award approval.")
        snapshot=eligibility(student,fund)
        if not snapshot["eligible"]: raise ValidationError(snapshot["reasons"])
        amount=Decimal(amount or 0)
        if not amount.is_finite() or amount<=0 or amount>min(item.requested_amount,fund.maximum_award) or amount!=amount.quantize(Decimal("0.01")): raise ValidationError("Award must be positive and no greater than the request and current fund limit.")
        if amount>fund.budget-fund.committed: raise ValidationError("The fund has insufficient uncommitted budget.")
        aid=FinancialAidAward.objects.create(student=student,name=fund.name,amount=amount,status="approved",visible=True)
        snapshot.update(fund_name=fund.name,term_id=fund.term_id,maximum_award=str(fund.maximum_award),budget=str(fund.budget),decision_reason=reason)
        ScholarshipAward.objects.create(application=item,fund=fund,aid=aid,amount=amount,approval_snapshot=snapshot)
    item.status=outcome;item.save(update_fields=["status"]);event(item,outcome,reason,actor)
    return item


@transaction.atomic
def change_award(award,action,reason,actor):
    fund,student,item=lock_application(award.application)
    award=ScholarshipAward.objects.select_for_update().get(pk=award.pk)
    target={"post":"disbursed","cancel":"cancelled","reverse":"revoked"}.get(action)
    if not target or not reason.strip(): raise ValidationError("An action and reason are required.")
    if award.status==target: return award
    if action=="post":
        if award.status!="approved": raise ValidationError("Only an approved award can be posted.")
        if student.status!="active" or not student.user.is_active: raise ValidationError("Reconcile the student's inactive status before posting.")
        award.credit=LedgerEntry.objects.create(student=student,description=f"Scholarship: {award.aid.name}"[:200],amount=-award.amount,posted=timezone.localdate(),released=True)
        award.aid.status="disbursed"
    elif action=="cancel":
        if award.status!="approved": raise ValidationError("Only an unposted award can be cancelled.")
        award.aid.status="cancelled"
    else:
        if award.status!="disbursed": raise ValidationError("Only a posted award can be reversed.")
        award.reversal=LedgerEntry.objects.create(student=student,description=f"Scholarship reversal #{award.pk}",amount=award.amount,posted=timezone.localdate(),released=True)
        award.aid.status="cancelled"
    award.status=target;award.save(update_fields=["status","credit","reversal"])
    award.aid.save(update_fields=["status"]);event(item,target,reason,actor)
    return award
