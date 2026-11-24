from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Department, Program, Term, Course, Enrollment
from .registrar import StudentProfile, RegistrationWindow, Application

class RegistrarTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.student=U.objects.create_user("student")
        self.other=U.objects.create_user("other")
        teacher=U.objects.create_user("teacher")
        today=timezone.localdate()
        now=timezone.now()
        d=Department.objects.create(name="Theology")
        self.program=Program.objects.create(department=d,name="Biblical Studies")
        t=Term.objects.create(name="Fall",starts=today,ends=today+timedelta(days=90))
        self.course=Course.objects.create(code="BIB101",title="Introduction",department=d,term=t,instructor=teacher,published=True)
        self.window=RegistrationWindow.objects.create(course=self.course,opens=now-timedelta(days=1),closes=now+timedelta(days=1),capacity=1)
        self.profile=StudentProfile.objects.create(user=self.student,student_number="TEST001",program=self.program,admitted_on=today)
        self.client.force_login(self.student)
    def test_registration(self):
        url=reverse("register",args=[self.window.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertEqual(Enrollment.objects.count(),1)
    def test_registration_hold(self):
        self.profile.registration_hold=True
        self.profile.save()
        self.assertEqual(self.client.post(reverse("register",args=[self.window.pk])).status_code,403)
    def test_full_course(self):
        Enrollment.objects.create(student=self.other,course=self.course)
        self.assertEqual(self.client.post(reverse("register",args=[self.window.pk])).status_code,403)
    def test_record_is_private(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("student_record")),"TEST001")
    def test_application_is_private(self):
        Application.objects.create(applicant=self.other,program=self.program,statement="Private statement")
        self.assertNotContains(self.client.get(reverse("admissions")),"Private statement")
        self.assertEqual(self.client.post(reverse("admissions"),{"program":self.program.pk,"statement":"My application"}).status_code,302)
        self.assertEqual(Application.objects.filter(applicant=self.student).count(),1)
