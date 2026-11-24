from django.contrib import admin
from .models import Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission
# Only superusers have access by default. Delegate model permissions carefully.
for model in [Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission]:
    admin.site.register(model)
admin.site.site_header = "FTBI Administration"

from .registrar import StudentProfile, RegistrationWindow, Application
for model in [StudentProfile, RegistrationWindow, Application]:
    admin.site.register(model)

from .services import FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource
for model in [FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource]:
    admin.site.register(model)

from .quizzes import Quiz, Question, Attempt
for model in [Quiz, Question, Attempt]:
    admin.site.register(model)
