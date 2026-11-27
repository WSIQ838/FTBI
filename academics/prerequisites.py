from django.db import models
from .models import Course
from .registrar import StudentProfile
from django.core.validators import MinValueValidator,MaxValueValidator

class Prerequisite(models.Model):
    group=models.CharField(max_length=40,blank=True,help_text="Rules in the same nonempty group are alternatives; all groups must be met.")
    kind=models.CharField(max_length=12,default="prerequisite",choices=[("prerequisite","Prior completion"),("corequisite","Prior completion or concurrent enrollment")])
    minimum_points=models.DecimalField(max_digits=3,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0),MaxValueValidator(4)])
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="prerequisites")
    required_code=models.CharField(max_length=30)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["course","required_code"],name="unique_prerequisite")]

class WaitlistEntry(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE)
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    joined=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["course","student"],name="unique_waitlist")]
        ordering=["joined","pk"]

def prerequisites_met(profile,course,concurrent_courses=()):
    from .services import FinalGrade
    from .operations import TransferCredit
    from .models import Enrollment
    groups={}
    for rule in course.prerequisites.all():
        grades=FinalGrade.objects.filter(student=profile,released=True,credits_earned__gt=0,course__code=rule.required_code)
        if rule.minimum_points is not None: grades=grades.filter(quality_points__gte=rule.minimum_points)
        met=grades.exists()
        if rule.minimum_points is None:
            met=met or TransferCredit.objects.filter(student=profile,approved=True,credits__gt=0,equivalent_code=rule.required_code).exists()
        if rule.kind=="corequisite":
            met=met or Enrollment.objects.filter(student=profile.user,active=True,course__term=course.term,course__code=rule.required_code).exists()
            met=met or any(candidate.pk!=course.pk and candidate.term_id==course.term_id and candidate.code==rule.required_code for candidate in concurrent_courses)
        groups.setdefault(rule.group or f"rule-{rule.pk}",[]).append(met)
    return all(any(options) for options in groups.values())
