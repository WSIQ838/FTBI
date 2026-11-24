from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Enrollment,Lesson
class ExperienceTests(TestCase):
    def test_search_respects_enrollment(self):
        U=get_user_model()
        teacher=U.objects.create_user("teacher")
        student=U.objects.create_user("student")
        date=timezone.localdate()
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Test",starts=date,ends=date)
        c=Course.objects.create(code="T1",title="PrivateCourse",department=d,term=t,instructor=teacher,published=True)
        Lesson.objects.create(course=c,title="PrivateLesson",body="Secret")
        self.client.force_login(student)
        self.assertNotContains(self.client.get(reverse("search"),{"q":"Private"}),"PrivateCourse")
        Enrollment.objects.create(student=student,course=c)
        self.assertContains(self.client.get(reverse("search"),{"q":"Private"}),"PrivateLesson")
        self.assertEqual(self.client.get(reverse("notifications")).status_code,200)
