from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    def __str__(self): return self.name

class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    required_credits = models.PositiveIntegerField(default=120)
    def __str__(self): return self.name

class Term(models.Model):
    name = models.CharField(max_length=100, unique=True)
    starts = models.DateField()
    ends = models.DateField()
    def clean(self):
        if self.starts and self.ends and self.ends < self.starts:
            raise ValidationError("End date precedes start date.")
    def __str__(self): return self.name

class Course(models.Model):
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    term = models.ForeignKey(Term, on_delete=models.PROTECT)
    section = models.CharField(max_length=20, default="01")
    credits = models.PositiveSmallIntegerField(default=3)
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teaching")
    syllabus = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["code","term","section"], name="unique_course_section")]
    def __str__(self): return f"{self.code} - {self.title} ({self.section})"

class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["student","course"], name="unique_enrollment")]
    def __str__(self): return f"{self.student} / {self.course}"

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    body = models.TextField()
    position = models.PositiveIntegerField(default=1)
    class Meta:
        ordering = ["position","pk"]
    def __str__(self): return self.title

class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    due = models.DateTimeField()
    def __str__(self): return self.title

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submissions")
    body = models.TextField()
    submitted_at = models.DateTimeField(auto_now=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0),MaxValueValidator(100)])
    feedback = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment","student"], name="unique_submission")]
    def __str__(self): return f"{self.assignment} / {self.student}"

from .registrar import StudentProfile, RegistrationWindow, Application

from .services import FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource

from .quizzes import Quiz, Question, Attempt

from .degree import DegreeRequirement, GraduationApplication

from .gradebook import GradeCategory, AssignmentWeight
