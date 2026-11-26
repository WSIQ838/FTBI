"""Versioned institutional policy review and voluntary demographic collection."""
import re
from django.conf import settings
from django.db import models,transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from .registrar import StudentProfile
from .operations import AuditEvent


def validate_questions(configuration):
    if not isinstance(configuration,dict) or set(configuration)!={"questions"}: raise ValidationError("Demographic configuration requires only a questions list.")
    questions=configuration["questions"]
    if not isinstance(questions,list) or not 1<=len(questions)<=4: raise ValidationError("Configure one to four voluntary choice questions.")
    keys=set()
    for question in questions:
        if not isinstance(question,dict) or set(question)!={"key","label","choices"}: raise ValidationError("Each question requires key, label and choices.")
        key=question["key"]
        if not isinstance(key,str) or key not in {"age_band","gender","first_generation","residency_country"} or key in keys: raise ValidationError("Use distinct supported demographic question keys.")
        keys.add(key)
        if not isinstance(question["label"],str) or not 1<=len(question["label"])<=150: raise ValidationError("Question labels must be 1–150 characters.")
        choices=question["choices"]
        if not isinstance(choices,list) or not 2<=len(choices)<=250: raise ValidationError("Each question needs 2–250 coded choices.")
        codes=set()
        for choice in choices:
            if not isinstance(choice,dict) or set(choice)!={"code","label"} or not isinstance(choice["code"],str) or not re.fullmatch(r"[a-z0-9_]{1,30}",choice["code"]) or choice["code"] in codes or not isinstance(choice["label"],str) or not 1<=len(choice["label"])<=100: raise ValidationError("Choice codes must be unique lowercase identifiers with short labels.")
            codes.add(choice["code"])
        if "prefer_not" not in codes: raise ValidationError("Each question must include a prefer_not choice.")


class InstitutionPolicy(models.Model):
    code=models.SlugField(max_length=60,unique=True)
    title=models.CharField(max_length=150)
    kind=models.CharField(max_length=20,choices=[(x,x.title()) for x in ["academic","finance","privacy","security","institutional","demographics"]])
    def __str__(self): return self.title
    def clean(self):
        if self.pk and self.revisions.exists():
            previous=type(self).objects.get(pk=self.pk)
            if (previous.kind,previous.code)!=(self.kind,self.code): raise ValidationError("Policy code and kind cannot change after a revision exists.")
    def current_revision(self):
        row=self.revisions.filter(review__approved=True,effective_from__lte=timezone.localdate()).order_by("-version").first()
        if not row or hasattr(row,"withdrawal") or (row.expires and row.expires<timezone.localdate()): return None
        return row


class PolicyRevision(models.Model):
    policy=models.ForeignKey(InstitutionPolicy,on_delete=models.PROTECT,related_name="revisions")
    version=models.PositiveIntegerField()
    title=models.CharField(max_length=150)
    body=models.TextField(max_length=12000)
    configuration=models.JSONField(default=dict,blank=True)
    effective_from=models.DateField()
    expires=models.DateField(null=True,blank=True)
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["policy","version"],name="unique_policy_version")]
    def clean(self):
        if self.expires and self.effective_from and self.expires<self.effective_from: raise ValidationError("Expiry precedes the effective date.")
        if self.policy_id and self.policy.kind=="demographics": validate_questions(self.configuration)
        elif self.configuration: raise ValidationError("Only demographic policies have executable configuration in this version.")
    def save(self,*args,**kwargs):
        if self.pk: raise ValueError("Policy revisions are immutable; create a new version.")
        super().save(*args,**kwargs)


class PolicyReview(models.Model):
    revision=models.OneToOneField(PolicyRevision,on_delete=models.PROTECT,related_name="review")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    approved=models.BooleanField()
    reason=models.TextField(max_length=2000)
    authority_reference=models.CharField(max_length=200)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        permissions=[("approve_institution_policy","Approve or withdraw institutional policy revisions")]


class PolicyWithdrawal(models.Model):
    revision=models.OneToOneField(PolicyRevision,on_delete=models.PROTECT,related_name="withdrawal")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    reason=models.TextField(max_length=2000)
    created=models.DateTimeField(auto_now_add=True)


class PolicyAcknowledgment(models.Model):
    revision=models.ForeignKey(PolicyRevision,on_delete=models.PROTECT)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["revision","user"],name="one_policy_acknowledgment")]


class DemographicCollection(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    enabled=models.BooleanField(default=False)
    policy=models.ForeignKey(InstitutionPolicy,on_delete=models.PROTECT,null=True,blank=True,limit_choices_to={"kind":"demographics"})
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(id=1),name="demographic_collection_singleton")]
        permissions=[("view_demographic_aggregates","View restricted demographic aggregate counts")]
    def clean(self):
        if self.policy_id and self.policy.kind!="demographics": raise ValidationError("Choose a demographic policy.")
        if self.enabled and (not self.policy_id or not self.policy.current_revision()): raise ValidationError("Enable only under a currently effective approved demographic policy.")


class DemographicResponse(models.Model):
    student=models.OneToOneField(StudentProfile,on_delete=models.CASCADE)
    revision=models.ForeignKey(PolicyRevision,on_delete=models.PROTECT)
    answers=models.JSONField(default=dict,blank=True)
    consented_at=models.DateTimeField()
    updated=models.DateTimeField(auto_now=True)


@transaction.atomic
def propose_revision(policy,author,body,configuration,effective_from,expires=None):
    policy=InstitutionPolicy.objects.select_for_update().get(pk=policy.pk)
    version=(policy.revisions.order_by("-version").values_list("version",flat=True).first() or 0)+1
    item=PolicyRevision(policy=policy,version=version,title=policy.title,body=body,configuration=configuration,effective_from=effective_from,expires=expires,author=author)
    item.full_clean();item.save()
    AuditEvent.objects.create(actor=author,action="policy_revision_proposed",target=str(item.pk))
    return item


@transaction.atomic
def decide_policy(revision,user,approved,reason,authority):
    revision=PolicyRevision.objects.select_for_update().get(pk=revision.pk)
    if not user.is_staff or not user.has_perm("academics.approve_institution_policy") or revision.author_id==user.pk: raise PermissionDenied("A different authorized policy reviewer is required.")
    revision.full_clean()
    prior=PolicyReview.objects.filter(revision=revision).first()
    if prior:
        if prior.approved!=approved: raise ValidationError("A different decision has already been recorded.")
        return prior
    review=PolicyReview(revision=revision,reviewer=user,approved=approved,reason=reason.strip(),authority_reference=authority.strip())
    review.full_clean();review.save()
    AuditEvent.objects.create(actor=user,action="policy_approved" if approved else "policy_rejected",target=str(revision.pk))
    return review


@transaction.atomic
def withdraw_policy(revision,user,reason):
    revision=PolicyRevision.objects.select_for_update().get(pk=revision.pk)
    if not user.is_staff or not user.has_perm("academics.approve_institution_policy"): raise PermissionDenied()
    if not PolicyReview.objects.filter(revision=revision,approved=True).exists(): raise ValidationError("Only an approved revision can be withdrawn.")
    if not reason.strip(): raise ValidationError("Withdrawal reason is required.")
    item,created=PolicyWithdrawal.objects.get_or_create(revision=revision,defaults={"actor":user,"reason":reason})
    if created: AuditEvent.objects.create(actor=user,action="policy_withdrawn",target=str(revision.pk))
    return item


def active_collection():
    control=DemographicCollection.objects.filter(pk=1,enabled=True).select_related("policy").first()
    if not control or not control.policy_id: return None
    revision=control.policy.current_revision()
    if revision: revision.full_clean()
    return revision


@transaction.atomic
def save_demographics(student,revision,answers):
    # Serialize against review/withdrawal for this revision; recheck current authority before saving.
    PolicyRevision.objects.select_for_update().get(pk=revision.pk)
    StudentProfile.objects.select_for_update().get(pk=student.pk)
    current=active_collection()
    if not current or current.pk!=revision.pk: raise ValidationError("The collection policy changed. Review it again before submitting.")
    keys={q["key"]:{c["code"] for c in q["choices"]} for q in current.configuration["questions"]}
    if not isinstance(answers,dict) or any(key not in keys or value not in keys[key] for key,value in answers.items()): raise ValidationError("Use only the approved answer choices.")
    item,_=DemographicResponse.objects.update_or_create(student=student,defaults={"revision":current,"answers":answers,"consented_at":timezone.now()})
    AuditEvent.objects.create(actor=student.user,action="demographic_response_saved",target=str(student.pk))
    return item


@transaction.atomic
def withdraw_demographics(student):
    StudentProfile.objects.select_for_update().get(pk=student.pk)
    count,_=DemographicResponse.objects.filter(student=student).delete()
    if count: AuditEvent.objects.create(actor=student.user,action="demographic_response_withdrawn",target=str(student.pk))


def demographic_counts(user):
    if not user.is_staff or not user.has_perm("academics.view_demographic_aggregates"): raise PermissionDenied()
    revision=active_collection()
    if not revision: return []
    questions=revision.configuration["questions"]
    counters={q["key"]:{choice["code"]:0 for choice in q["choices"]} for q in questions}
    for answers in DemographicResponse.objects.filter(revision=revision).values_list("answers",flat=True).iterator():
        for key,counts in counters.items():
            if answers.get(key) in counts: counts[answers[key]]+=1
    panels=[]
    for question in questions:
        counts=counters[question["key"]]
        # Withhold the whole question if any nonzero cell is small, including its total.
        suppressed=any(0<count<5 for count in counts.values())
        panels.append({"label":question["label"],"suppressed":suppressed,"rows":[] if suppressed else [{"label":choice["label"],"count":counts[choice["code"]]} for choice in question["choices"]]})
    AuditEvent.objects.create(actor=user,action="demographic_aggregates_viewed",target=str(revision.pk))
    return panels
