from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse
from .models import Department,Term,Course,Enrollment,Assignment,Submission

class AttachmentTests(TestCase):
    def test_private_download(self):
        U=get_user_model()
        student=U.objects.create_user("student")
        teacher=U.objects.create_user("teacher")
        other=U.objects.create_user("other")
        today=timezone.localdate()
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Test",starts=today,ends=today)
        c=Course.objects.create(code="T",title="Test",department=d,term=t,instructor=teacher,published=True)
        Enrollment.objects.create(student=student,course=c)
        a=Assignment.objects.create(course=c,title="Test",instructions="Test",due=timezone.now()+timedelta(days=1))
        s=Submission.objects.create(assignment=a,student=student,body="Test")
        self.client.force_login(student)
        self.assertEqual(self.client.post(reverse("upload_attachment",args=[s.pk]),{"file":SimpleUploadedFile("work.txt",b"Private work")}).status_code,302)
        url=reverse("download_attachment",args=[s.pk])
        self.assertEqual(self.client.get(url).content,b"Private work")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(url).content,b"Private work")
