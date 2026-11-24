from django.db import models
from .models import Course
from .registrar import StudentProfile

class Prerequisite(models.Model):
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

def prerequisites_met(profile,course):
    from .services import FinalGrade
    from .operations import TransferCredit
    required=set(course.prerequisites.values_list("required_code",flat=True))
    passed=set(FinalGrade.objects.filter(student=profile,released=True,credits_earned__gt=0).values_list("course__code",flat=True))
    passed.update(TransferCredit.objects.filter(student=profile,approved=True,credits__gt=0).values_list("equivalent_code",flat=True))
    return required.issubset(passed)
