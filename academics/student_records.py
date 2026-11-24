import uuid
from decimal import Decimal,InvalidOperation
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator,MaxValueValidator
from .models import Course,Program,Term,Enrollment
from .registrar import StudentProfile


class WithdrawalWindow(models.Model):
    course=models.OneToOneField(Course,on_delete=models.PROTECT)
    opens=models.DateTimeField()
    closes=models.DateTimeField()
    def clean(self):
        if self.opens and self.closes and self.closes<=self.opens: raise ValidationError("Withdrawal must close after opening.")


class WithdrawalRequest(models.Model):
    enrollment=models.OneToOneField(Enrollment,on_delete=models.PROTECT)
    reason=models.TextField(max_length=2000)
    status=models.CharField(max_length=12,default="pending",choices=[("pending","Pending"),("approved","Approved"),("denied","Denied")])
    requested=models.DateTimeField(auto_now_add=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    reviewed_at=models.DateTimeField(null=True)


class GradingScale(models.Model):
    program=models.OneToOneField(Program,on_delete=models.PROTECT)
    name=models.CharField(max_length=100)
    entries=models.JSONField(help_text='List of objects: {"minimum":90,"letter":"A","points":4,"passing":true}. Include a zero threshold; thresholds and letters must be unique.')
    active=models.BooleanField(default=False)
    approval_reference=models.CharField(max_length=200)
    def clean(self):
        try:
            if not isinstance(self.entries,list) or not 1<=len(self.entries)<=30: raise ValueError()
            limits=[]; letters=[]
            for entry in self.entries:
                if set(entry)!={"minimum","letter","points","passing"}: raise ValueError()
                minimum=Decimal(str(entry["minimum"])); points=Decimal(str(entry["points"]))
                if not minimum.is_finite() or not points.is_finite() or not 0<=minimum<=100 or not 0<=points<=4 or type(entry["passing"]) is not bool or not isinstance(entry["letter"],str) or not 1<=len(entry["letter"])<=10: raise ValueError()
                limits.append(minimum); letters.append(entry["letter"])
            if 0 not in limits or len(set(limits))!=len(limits) or len(set(letters))!=len(letters): raise ValueError()
        except (ValueError,TypeError,KeyError,InvalidOperation):
            raise ValidationError("Enter unique grading thresholds from 0 through 100, unique letters, points from 0 through 4 and boolean passing flags.")

    def grade(self,score):
        score=Decimal(score)
        if not score.is_finite() or not 0<=score<=100: raise ValidationError("Score must be between 0 and 100.")
        return max((entry for entry in self.entries if Decimal(str(entry["minimum"]))<=score),key=lambda entry:Decimal(str(entry["minimum"])))


class StandingPolicy(models.Model):
    program=models.OneToOneField(Program,on_delete=models.PROTECT)
    minimum_gpa=models.DecimalField(max_digits=3,decimal_places=2,default=2,validators=[MinValueValidator(0),MaxValueValidator(4)])
    enabled=models.BooleanField(default=False)
    approval_reference=models.CharField(max_length=200)


class AcademicStanding(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    term=models.ForeignKey(Term,on_delete=models.PROTECT)
    gpa=models.DecimalField(max_digits=3,decimal_places=2,null=True)
    status=models.CharField(max_length=12,choices=[("good","Good standing"),("probation","Probation"),("unassessed","No GPA grades")])
    policy_snapshot=models.JSONField()
    calculated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)


class EmergencyContact(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.CASCADE,related_name="emergency_contacts")
    name=models.CharField(max_length=150)
    relationship=models.CharField(max_length=100)
    phone=models.CharField(max_length=50)
    email=models.EmailField(blank=True)


class StudentStatusRecord(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT,related_name="status_history")
    previous=models.CharField(max_length=16,blank=True)
    current=models.CharField(max_length=16)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    created=models.DateTimeField(auto_now_add=True)


class EnrollmentVerification(models.Model):
    identifier=models.UUIDField(default=uuid.uuid4,unique=True)
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    issued=models.DateTimeField(auto_now_add=True)


def standing_for(student,term,actor):
    from .services import FinalGrade
    policy=StandingPolicy.objects.filter(program=student.program,enabled=True).first()
    if not policy: raise ValidationError("An approved standing policy must be enabled for this program.")
    grades=FinalGrade.objects.filter(student=student,released=True,quality_points__isnull=False,course__term__ends__lte=term.ends).select_related("course")
    credits=sum(g.course.credits for g in grades)
    gpa=sum((g.quality_points*g.course.credits for g in grades),Decimal(0))/credits if credits else None
    return AcademicStanding.objects.create(student=student,term=term,gpa=gpa.quantize(Decimal("0.01")) if gpa is not None else None,status="unassessed" if gpa is None else "probation" if gpa<policy.minimum_gpa else "good",policy_snapshot={"minimum_gpa":str(policy.minimum_gpa),"approval":policy.approval_reference,"attempted_credits":credits},calculated_by=actor)
