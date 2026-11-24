from django.db import models
from .models import Program
from .registrar import StudentProfile

class DegreeRequirement(models.Model):
    program=models.ForeignKey(Program,on_delete=models.CASCADE,related_name="requirements")
    course_code=models.CharField(max_length=30)
    title=models.CharField(max_length=200)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["program","course_code"],name="unique_program_course")]

class GraduationApplication(models.Model):
    student=models.OneToOneField(StudentProfile,on_delete=models.PROTECT)
    requested=models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=16,choices=[("pending","Pending"),("approved","Approved"),("denied","Denied")],default="pending")
