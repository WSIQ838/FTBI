from django.conf import settings
from django.db import models
from .models import Course
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

class Quiz(models.Model):
    results_released=models.BooleanField(default=True)
    course=models.ForeignKey(Course,on_delete=models.CASCADE)
    title=models.CharField(max_length=200)
    published=models.BooleanField(default=False)
    closes=models.DateTimeField()
    def __str__(self): return self.title

class QuestionDefinition(models.Model):
    kind=models.CharField(max_length=12,default="choice",choices=[("choice","Multiple choice"),("boolean","True / false"),("essay","Essay (manual grading)"),("short","Short answer"),("blank","Fill in the blank"),("matching","Matching")])
    points=models.PositiveSmallIntegerField(default=1,validators=[MinValueValidator(1),MaxValueValidator(1000)])
    prompt=models.TextField()
    option_a=models.CharField(max_length=500,blank=True)
    option_b=models.CharField(max_length=500,blank=True)
    option_c=models.CharField(max_length=500,blank=True)
    option_d=models.CharField(max_length=500,blank=True)
    correct=models.CharField(max_length=1,blank=True,choices=[(x,x) for x in "ABCD"])
    answer_key=models.JSONField(default=list,blank=True,help_text='Short/blank: JSON list of accepted answers. True/false: [true] or [false]. Matching: JSON object mapping prompts to matching values. Essay: leave empty.')

    class Meta:
        abstract=True

    def clean(self):
        super().clean()
        if self.kind == "choice" and (self.correct not in "ABCD" or not self.correct or not all([self.option_a,self.option_b,self.option_c,self.option_d])):
            raise ValidationError("Multiple choice requires four options and a correct choice.")
        if self.kind == "boolean" and (not isinstance(self.answer_key,list) or len(self.answer_key)!=1 or type(self.answer_key[0]) is not bool):
            raise ValidationError("True/false requires [true] or [false].")
        if self.kind in ("short","blank") and (not isinstance(self.answer_key,list) or not 1<=len(self.answer_key)<=20 or not all(isinstance(a,str) and a.strip() and len(a)<=500 for a in self.answer_key)):
            raise ValidationError("Provide 1–20 nonempty accepted answers, at most 500 characters each.")
        if self.kind == "matching" and (not isinstance(self.answer_key,dict) or not 2<=len(self.answer_key)<=20 or not all(isinstance(k,str) and k.strip() and len(k)<=500 and isinstance(v,str) and v.strip() and len(v)<=500 for k,v in self.answer_key.items())):
            raise ValidationError("Matching requires 2–20 prompt/value pairs, at most 500 characters each.")


class Question(QuestionDefinition):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE,related_name="questions")

class Attempt(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.PROTECT)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    number=models.PositiveSmallIntegerField(default=1)
    score=models.DecimalField(max_digits=12,decimal_places=2)
    total=models.DecimalField(max_digits=12,decimal_places=2)
    graded=models.BooleanField(default=True)
    submitted=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["quiz","student","number"],name="unique_numbered_attempt")]


class AttemptAnswer(models.Model):
    attempt=models.ForeignKey(Attempt,on_delete=models.PROTECT,related_name="answers")
    question=models.ForeignKey(Question,on_delete=models.PROTECT)
    response=models.JSONField()
    possible=models.PositiveSmallIntegerField()
    earned=models.DecimalField(max_digits=7,decimal_places=2,null=True,blank=True)
    feedback=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["attempt","question"],name="unique_attempt_answer")]
