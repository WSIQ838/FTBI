from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
from .quizzes import Quiz, QuestionDefinition

class ExamAccommodation(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    extra_minutes=models.PositiveIntegerField(default=0,validators=[MaxValueValidator(720)])
    extra_attempts=models.PositiveSmallIntegerField(default=0,validators=[MaxValueValidator(5)])
    extended_close=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student"],name="unique_exam_accommodation")]

class BankQuestion(QuestionDefinition):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    def __str__(self): return self.prompt[:100]
