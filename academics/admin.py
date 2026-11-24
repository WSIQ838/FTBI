from django.contrib import admin
from .models import Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission
# Only superusers have access by default. Delegate model permissions carefully.
for model in [Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission]:
    admin.site.register(model)
admin.site.site_header = "FTBI Administration"
