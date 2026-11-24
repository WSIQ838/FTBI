from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
from .quizzes import Quiz

class ExamAccommodation(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    extra_minutes=models.PositiveIntegerField(default=0,validators=[MaxValueValidator(720)])
    extra_attempts=models.PositiveSmallIntegerField(default=0,validators=[MaxValueValidator(5)])
    extended_close=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student"],name="unique_exam_accommodation")]

class BankQuestion(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    prompt=models.TextField()
    option_a=models.CharField(max_length=500)
    option_b=models.CharField(max_length=500)
    option_c=models.CharField(max_length=500)
    option_d=models.CharField(max_length=500)
    correct=models.CharField(max_length=1,choices=[(x,x) for x in "ABCD"])
    def __str__(self): return self.prompt[:100]
