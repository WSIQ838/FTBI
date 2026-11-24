from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Department, Term, Course, Enrollment, Assignment, Submission

class AccessTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.teacher = U.objects.create_user("teacher")
        self.student = U.objects.create_user("student")
        self.other = U.objects.create_user("other")
        today = timezone.localdate()
        d = Department.objects.create(name="General Studies")
        t = Term.objects.create(name="Fall", starts=today, ends=today+timedelta(days=90))
        self.course = Course.objects.create(code="GEN101",title="Introduction",department=d,term=t,instructor=self.teacher,published=True)
        Enrollment.objects.create(student=self.student,course=self.course)
        self.assignment = Assignment.objects.create(course=self.course,title="Essay",instructions="Write an essay",due=timezone.now()+timedelta(days=1))
    def test_anonymous_redirect(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code,302)
    def test_unenrolled_denied(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("course",args=[self.course.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse("submit",args=[self.assignment.pk]),{"body":"test"}).status_code,404)
    def test_student_submission_and_teacher_grade(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("submit",args=[self.assignment.pk]),{"body":"Essay"}).status_code,302)
        s = Submission.objects.get()
        self.assertEqual(self.client.post(reverse("grade",args=[s.pk]),{"grade":99}).status_code,404)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(reverse("grade",args=[s.pk]),{"grade":95,"feedback":"Good"}).status_code,302)
        s.refresh_from_db()
        self.assertEqual(s.grade,95)
    def test_unpublished_hidden(self):
        self.course.published=False
        self.course.save()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("course",args=[self.course.pk])).status_code,404)
