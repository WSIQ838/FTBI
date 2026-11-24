from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
from .models import Assignment, Course, Submission

class GradeCategory(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="grade_categories")
    name=models.CharField(max_length=100)
    weight=models.DecimalField(max_digits=5,decimal_places=2,validators=[MinValueValidator(0),MaxValueValidator(100)])
    class Meta:
        constraints=[models.UniqueConstraint(fields=["course","name"],name="unique_grade_category")]

class AssignmentWeight(models.Model):
    assignment=models.OneToOneField(Assignment,on_delete=models.CASCADE)
    category=models.ForeignKey(GradeCategory,on_delete=models.PROTECT)
    points=models.PositiveIntegerField(default=100,validators=[MinValueValidator(1)])
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.assignment.course_id != self.category.course_id:
            raise ValidationError("Category must belong to the assignment course.")

def current_grade(course,student):
    categories=list(course.grade_categories.all())
    if not categories or sum(c.weight for c in categories)!=Decimal(100):
        return None
    results=[]
    for category in categories:
        if not category.weight:
            continue
        weights=AssignmentWeight.objects.filter(category=category,assignment__course=course)
        scores={s.assignment_id:s.grade for s in Submission.objects.filter(student=student,assignment__course=course,grade__isnull=False)}
        earned=Decimal(0)
        possible=0
        for w in weights:
            if w.assignment_id in scores:
                earned+=scores[w.assignment_id]*w.points/100
                possible+=w.points
        if possible:
            results.append((earned/possible,category.weight))
    denominator=sum(w for _,w in results)
    return round(sum(s*w for s,w in results)*100/denominator,2) if denominator else None
