from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Course, Program
from .registrar import StudentProfile

class FinalGrade(models.Model):
    student = models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    course = models.ForeignKey(Course,on_delete=models.PROTECT)
    letter = models.CharField(max_length=10)
    credits_earned = models.PositiveSmallIntegerField(default=0)
    quality_points = models.DecimalField(max_digits=3,decimal_places=2,validators=[MinValueValidator(0),MaxValueValidator(4)],null=True,blank=True)
    released = models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","course"],name="unique_final_grade")]
    def clean(self):
        from django.core.exceptions import ValidationError
        from .student_records import GradingScale
        scale=GradingScale.objects.filter(program=self.student.program,active=True).first() if self.student_id else None
        allowed={entry["letter"] for entry in scale.entries} if scale else {"A","A-","B+","B","B-","C+","C","C-","D","F","P","NP"}
        if self.letter not in allowed|{"W","I"}: raise ValidationError("Grade is not in the program's grading scale.")
        if self.course_id and self.credits_earned is not None and self.credits_earned > self.course.credits:
            raise ValidationError("Earned credits exceed course credits.")
        if self.letter in {"W","I"} and (self.quality_points is not None or self.credits_earned):
            raise ValidationError("Withdrawal and incomplete grades cannot award credits or GPA points.")

class Attendance(models.Model):
    student = models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    course = models.ForeignKey(Course,on_delete=models.PROTECT)
    date = models.DateField()
    status = models.CharField(max_length=12,choices=[(x,x.title()) for x in ["present","absent","late","excused"]])
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","course","date"],name="unique_attendance_day")]

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    course = models.ForeignKey(Course,on_delete=models.CASCADE,null=True,blank=True)
    published = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    starts = models.DateTimeField()
    ends = models.DateTimeField()
    course = models.ForeignKey(Course,on_delete=models.CASCADE,null=True,blank=True)
    published = models.BooleanField(default=False)

class LedgerEntry(models.Model):
    student = models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12,decimal_places=2,help_text="Positive charge; negative credit or payment")
    posted = models.DateField()
    released = models.BooleanField(default=False)

class AdvisingNote(models.Model):
    student = models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    advisor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    note = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

class Practicum(models.Model):
    student = models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    activity = models.CharField(max_length=200)
    date = models.DateField()
    hours = models.DecimalField(max_digits=6,decimal_places=2,validators=[MinValueValidator(0)])
    approved = models.BooleanField(default=False)

class LearningOutcome(models.Model):
    program = models.ForeignKey(Program,on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    evidence = models.TextField(blank=True)
    assessed_on = models.DateField(null=True,blank=True)

class LibraryResource(models.Model):
    title = models.CharField(max_length=200)
    url = models.URLField()
    description = models.TextField(blank=True)
    published = models.BooleanField(default=False)
