from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Department,Program
from .registrar import StudentProfile
from .payments import PaymentRequest

class PaymentTests(TestCase):
    def test_receipt_never_verifies_itself(self):
        U=get_user_model()
        student=U.objects.create_user("student")
        d=Department.objects.create(name="Test")
        p=Program.objects.create(name="Test",department=d)
        profile=StudentProfile.objects.create(user=student,student_number="TEST-PAY",program=p,admitted_on=timezone.localdate())
        self.client.force_login(student)
        self.assertEqual(self.client.post(reverse("payment_portal"),{"amount":"50","reference":"TEST","status":"verified"}).status_code,302)
        record=PaymentRequest.objects.get()
        self.assertEqual(record.student,profile)
        self.assertEqual(record.status,"pending")
