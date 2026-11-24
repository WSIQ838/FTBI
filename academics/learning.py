import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
from .models import Course,Lesson,Submission


class LearningModule(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="modules")
    title=models.CharField(max_length=200)
    position=models.PositiveIntegerField(default=1)
    prerequisites=models.ManyToManyField("self",symmetrical=False,blank=True)
    class Meta:
        ordering=["position","pk"]
    def __str__(self): return self.title


class LessonCompletion(models.Model):
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    lesson=models.ForeignKey(Lesson,on_delete=models.PROTECT,related_name="completions")
    completed=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","lesson"],name="unique_lesson_completion")]


class CompletionPolicy(models.Model):
    course=models.OneToOneField(Course,on_delete=models.CASCADE,related_name="completion_policy")
    enabled=models.BooleanField(default=False)
    minimum_score=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal(60),validators=[MinValueValidator(0),MaxValueValidator(100)])


class CourseCertificate(models.Model):
    identifier=models.UUIDField(default=uuid.uuid4,unique=True)
    student=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    course=models.ForeignKey(Course,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    issued=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","course"],name="unique_course_certificate")]


def module_open(module,student):
    """A module opens only after every prerequisite's lessons are complete."""
    if module is None: return True
    completed=set(LessonCompletion.objects.filter(student=student,lesson__course=module.course).values_list("lesson_id",flat=True))
    visited=set(); satisfied_modules=set()
    def satisfied(current):
        if current.pk in visited: return False
        if current.pk in satisfied_modules: return True
        visited.add(current.pk)
        for prerequisite in current.prerequisites.all():
            ids=set(prerequisite.lesson_set.values_list("pk",flat=True))
            if prerequisite.course_id!=module.course_id or not ids or not ids.issubset(completed) or not satisfied(prerequisite): return False
        visited.remove(current.pk)
        satisfied_modules.add(current.pk)
        return True
    return satisfied(module)


def course_complete(course,student):
    from .assessment_engine import attempt_grade
    policy=CompletionPolicy.objects.filter(course=course,enabled=True).first()
    if not policy: return False
    lessons=set(course.lessons.values_list("pk",flat=True))
    if not lessons or not lessons.issubset(set(LessonCompletion.objects.filter(student=student,lesson__course=course).values_list("lesson_id",flat=True))): return False
    for assignment in course.assignments.all():
        if not Submission.objects.filter(assignment=assignment,student=student,grade__gte=policy.minimum_score).exists(): return False
    for quiz in course.quiz_set.all():
        result=attempt_grade(quiz,student)
        if result is None or result<policy.minimum_score: return False
    return True
