from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program
from .registrar import StudentProfile
from .operations import TranscriptRequest
from .transcripts import IssuedTranscript

class TranscriptTests(TestCase):
    def test_issuance_and_privacy(self):
        U=get_user_model()
        student=U.objects.create_user("student")
        outsider=U.objects.create_user("outsider")
        registrar=U.objects.create_superuser("registrar",password="test-only-password")
        d=Department.objects.create(name="Test")
        p=Program.objects.create(name="Test",department=d)
        profile=StudentProfile.objects.create(user=student,student_number="TEST01",program=p,admitted_on=timezone.localdate())
        item=TranscriptRequest.objects.create(student=profile,destination="Personal copy")
        url=reverse("issue_transcript",args=[item.pk])
        self.client.force_login(student)
        self.assertEqual(self.client.post(url).status_code,403)
        self.client.force_login(registrar)
        self.assertEqual(self.client.post(url).status_code,302)
        record=IssuedTranscript.objects.get()
        self.assertEqual(len(record.digest),64)
        self.assertEqual(self.client.post(url).status_code,403)
        view=reverse("transcript",args=[record.identifier])
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(view).status_code,404)
        self.client.force_login(student)
        self.assertContains(self.client.get(view),"TEST01")
