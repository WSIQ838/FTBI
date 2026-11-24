from django.conf import settings
from django.db import models
from .models import Course

class Quiz(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE)
    title=models.CharField(max_length=200)
    published=models.BooleanField(default=False)
    closes=models.DateTimeField()
    def __str__(self): return self.title

class Question(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE,related_name="questions")
    prompt=models.TextField()
    option_a=models.CharField(max_length=500)
    option_b=models.CharField(max_length=500)
    option_c=models.CharField(max_length=500)
    option_d=models.CharField(max_length=500)
    correct=models.CharField(max_length=1,choices=[(x,x) for x in "ABCD"])

class Attempt(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.PROTECT)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    number=models.PositiveSmallIntegerField(default=1)
    score=models.PositiveIntegerField()
    total=models.PositiveIntegerField()
    submitted=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student","number"],name="unique_numbered_attempt")]
