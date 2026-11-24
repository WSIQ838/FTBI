from django.conf import settings
from django.db import models
from .quizzes import Quiz

class QuizPolicy(models.Model):
    quiz=models.OneToOneField(Quiz,on_delete=models.CASCADE,related_name="policy")
    minutes=models.PositiveIntegerField(default=60)
    shuffle=models.BooleanField(default=True)

class QuizSession(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.PROTECT)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    started=models.DateTimeField()
    expires=models.DateTimeField()
    question_ids=models.JSONField(default=list)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student"],name="unique_quiz_session")]
