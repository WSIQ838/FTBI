from django.conf import settings
from django.db import models
from .quizzes import Quiz
from django.core.validators import MinValueValidator, MaxValueValidator

class QuizPolicy(models.Model):
    max_attempts=models.PositiveSmallIntegerField(default=1,validators=[MinValueValidator(1),MaxValueValidator(20)])
    select_count=models.PositiveSmallIntegerField(default=0,help_text="0 selects every question.")
    attempt_rule=models.CharField(max_length=8,default="highest",choices=[("highest","Highest"),("latest","Latest"),("average","Average")])
    quiz=models.OneToOneField(Quiz,on_delete=models.CASCADE,related_name="policy")
    minutes=models.PositiveIntegerField(default=60,validators=[MinValueValidator(1),MaxValueValidator(1440)])
    shuffle=models.BooleanField(default=True)

class QuizSession(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.PROTECT)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    number=models.PositiveSmallIntegerField(default=1)
    started=models.DateTimeField()
    expires=models.DateTimeField()
    question_ids=models.JSONField(default=list)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student","number"],name="unique_numbered_session")]
