from datetime import timedelta
from django.test import TestCase,override_settings
from django.core.management import call_command
from django.core.cache import cache
from django.core import mail
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Department,Term,Course,Enrollment,Assignment

class ReminderTests(TestCase):
    @override_settings(FTBI_EMAIL_REMINDERS=True,SMTP_CONFIGURED=True,EMAIL_HOST="test",EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reminder_is_generic_and_not_repeated(self):
        cache.clear()
        U=get_user_model()
        teacher=U.objects.create_user("teacher")
        student=U.objects.create_user("student",email="student@example.invalid")
        date=timezone.localdate()
        d=Department.objects.create(name="Test")
        term=Term.objects.create(name="Test",starts=date,ends=date)
        course=Course.objects.create(code="T",title="Private course",department=d,term=term,instructor=teacher,published=True)
        Enrollment.objects.create(student=student,course=course)
        Assignment.objects.create(course=course,title="Private assignment",instructions="Test",due=timezone.now()+timedelta(hours=12))
        call_command("send_course_reminders")
        self.assertEqual(len(mail.outbox),1)
        self.assertNotIn("Private assignment",mail.outbox[0].body)
        cache.clear()
        call_command("send_course_reminders")
        self.assertEqual(len(mail.outbox),1)
        cache.clear()
