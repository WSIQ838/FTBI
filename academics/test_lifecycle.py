from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment
from .registrar import Application,StudentProfile,RegistrationWindow
from .prerequisites import WaitlistEntry
class LifecycleTests(TestCase):
    def test_admission_and_waitlist(self):
        U=get_user_model()
        registrar=U.objects.create_user("registrar")
        applicant=U.objects.create_user("applicant")
        second=U.objects.create_user("second")
        teacher=U.objects.create_user("teacher")
        d=Department.objects.create(name="Test")
        program=Program.objects.create(department=d,name="Test")
        application=Application.objects.create(applicant=applicant,program=program,statement="Test")
        self.client.force_login(applicant)
        self.assertEqual(self.client.post(reverse("admission_decide",args=[application.pk]),{"decision":"accepted"}).status_code,403)
        registrar.user_permissions.add(*Permission.objects.filter(content_type__app_label="academics",codename__in=["change_application","add_studentprofile"]))
        self.client.force_login(registrar)
        self.assertEqual(self.client.post(reverse("admission_decide",args=[application.pk]),{"decision":"accepted"}).status_code,302)
        self.assertEqual(self.client.post(reverse("activate_student",args=[application.pk])).status_code,302)
        profile=StudentProfile.objects.get(user=applicant)
        today=timezone.localdate()
        other=StudentProfile.objects.create(user=second,student_number="S2",program=program,admitted_on=today)
        term=Term.objects.create(name="Test",starts=today,ends=today)
        course=Course.objects.create(code="T",title="Test",department=d,term=term,instructor=teacher,published=True)
        RegistrationWindow.objects.create(course=course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),capacity=1)
        e=Enrollment.objects.create(student=applicant,course=course)
        WaitlistEntry.objects.create(student=other,course=course)
        self.client.force_login(applicant)
        self.assertContains(self.client.get(reverse("decision_letter",args=[application.pk])),"accepted")
        self.assertEqual(self.client.post(reverse("drop_course",args=[e.pk])).status_code,302)
        e.refresh_from_db()
        self.assertFalse(e.active)
        self.assertTrue(Enrollment.objects.filter(student=second,course=course,active=True).exists())
