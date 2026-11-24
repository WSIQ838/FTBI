from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from .models import Program, Course

class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="student_profile")
    student_number = models.CharField(max_length=32,unique=True)
    program = models.ForeignKey(Program,on_delete=models.PROTECT)
    admitted_on = models.DateField()
    status = models.CharField(max_length=16,choices=[("active","Active"),("leave","On leave"),("graduated","Graduated"),("withdrawn","Withdrawn")],default="active")
    registration_hold = models.BooleanField(default=False)
    def __str__(self): return self.student_number

class RegistrationWindow(models.Model):
    course = models.OneToOneField(Course,on_delete=models.CASCADE,related_name="registration")
    opens = models.DateTimeField()
    closes = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=30)
    def clean(self):
        if self.opens and self.closes and self.opens >= self.closes:
            raise ValidationError("Registration must close after opening.")
    def __str__(self): return str(self.course)

class Application(models.Model):
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    program = models.ForeignKey(Program,on_delete=models.PROTECT)
    statement = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16,choices=[("pending","Pending"),("accepted","Accepted"),("rejected","Rejected")],default="pending")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["applicant","program"],name="one_application_per_program")]
    def __str__(self): return f"{self.applicant} / {self.program}"
