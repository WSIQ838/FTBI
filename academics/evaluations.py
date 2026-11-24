from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Course

class EvaluationWindow(models.Model):
    course=models.OneToOneField(Course,on_delete=models.CASCADE)
    opens=models.DateTimeField()
    closes=models.DateTimeField()

class CourseEvaluation(models.Model):
    window=models.ForeignKey(EvaluationWindow,on_delete=models.PROTECT)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    rating=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])
    comments=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["window","student"],name="one_course_evaluation")]
