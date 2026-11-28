import os
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from academics.models import Department,Program,Term,Course,Lesson,Assignment,Enrollment,StudentProfile,AssignmentPolicy


class Command(BaseCommand):
    help="Create synthetic learning records in an empty, explicitly enabled development database."

    @transaction.atomic
    def handle(self,*args,**options):
        password=os.environ.get("FTBI_DEMO_PASSWORD","")
        if not settings.DEBUG or os.environ.get("FTBI_ALLOW_DEMO")!="1" or len(password)<16:
            raise CommandError("Demo generation requires DEBUG, FTBI_ALLOW_DEMO=1 and a 16+ character FTBI_DEMO_PASSWORD.")
        User=get_user_model()
        if User.objects.exists() or Department.objects.exists():
            raise CommandError("Demo generation requires an empty database; existing records will not be changed.")
        now=timezone.now()
        from academics.institution import InstitutionSettings
        InstitutionSettings.objects.create(name="FTBI Demonstration College",short_name="FTBI Demo")
        department=Department.objects.create(name="Demonstration Studies")
        program=Program.objects.create(department=department,name="Synthetic learning program",required_credits=3)
        term=Term.objects.create(name="Demonstration term",starts=now.date(),ends=(now+timedelta(days=90)).date())
        faculty=User.objects.create_user(username="demo-faculty",password=password,first_name="Demo",last_name="Faculty")
        course=Course.objects.create(code="DEMO101",title="Learning demonstration",department=department,term=term,instructor=faculty,published=True,syllabus="Synthetic records for validation only.")
        Lesson.objects.create(course=course,title="Welcome lesson",body="Read the lesson, then submit a short reflection.")
        assignment=Assignment.objects.create(course=course,title="Demonstration reflection",instructions="Describe what you learned.",due=now+timedelta(days=30))
        AssignmentPolicy.objects.create(assignment=assignment,max_submissions=20,allow_graded_resubmission=True)
        for index,name in enumerate(["chromium","firefox","webkit","mobile","dark","outsider"],1):
            student=User.objects.create_user(username="demo-"+name,password=password,first_name="Demo",last_name=name.title())
            StudentProfile.objects.create(user=student,student_number=f"DEMO-{index:04d}",program=program,admitted_on=now.date())
            if name!="outsider": Enrollment.objects.create(student=student,course=course)
        if os.environ.get("FTBI_BROWSER_TESTING")=="1":
            User.objects.create_user(username="demo-passkey",password=password,first_name="Demo",last_name="Passkey")
            from django.contrib.auth.models import Permission
            from academics.student_records import WithdrawalWindow,WithdrawalRequest
            reviewer=User.objects.create_user(username="demo-records-reviewer",password=password,first_name="Demo",last_name="Records reviewer")
            reviewer.user_permissions.set(Permission.objects.filter(content_type__app_label="academics",codename__in=["change_withdrawalappeal","change_enrollment","add_finalgrade"]))
            WithdrawalWindow.objects.create(course=course,opens=now-timedelta(days=1),closes=now+timedelta(days=1),appeal_days=7,appeal_approval_reference="SYNTHETIC BROWSER POLICY")
            for index,name in enumerate(["chromium","firefox","webkit","mobile","dark"],1):
                student=User.objects.create_user(username="demo-records-"+name,password=password,first_name="Demo",last_name="Records "+name)
                StudentProfile.objects.create(user=student,student_number=f"DEMO-RECORDS-{index:04d}",program=program,admitted_on=now.date())
                enrollment=Enrollment.objects.create(student=student,course=course)
                WithdrawalRequest.objects.create(enrollment=enrollment,reason="Synthetic denied request",status="denied",reviewed_by=faculty,reviewed_at=now)
        self.stdout.write("Created synthetic faculty, students, course, lesson and assignment. No external notifications sent.")
