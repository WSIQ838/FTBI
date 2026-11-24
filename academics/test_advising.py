from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,StudentProfile
from .advising import AdvisorAssignment
class AdvisingTests(TestCase):
    def test_caseload_scope(self):
        U=get_user_model()
        advisor=U.objects.create_user("advisor")
        other=U.objects.create_user("other")
        student=U.objects.create_user("student")
        program=Program.objects.create(department=Department.objects.create(name="Test"),name="Test")
        profile=StudentProfile.objects.create(user=student,student_number="S1",program=program,admitted_on=timezone.localdate())
        assignment=AdvisorAssignment.objects.create(student=profile,advisor=advisor)
        permission=Permission.objects.get(content_type__app_label="academics",codename="view_advisorassignment")
        advisor.user_permissions.add(permission)
        other.user_permissions.add(permission)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("advise",args=[assignment.pk])).status_code,404)
        self.client.force_login(advisor)
        self.assertEqual(self.client.post(reverse("advise",args=[assignment.pk]),{"note":"Meeting scheduled"}).status_code,302)
        self.assertContains(self.client.get(reverse("advise",args=[assignment.pk])),"Meeting scheduled")
