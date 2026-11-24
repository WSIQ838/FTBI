from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Enrollment
from .discussions import Discussion,DiscussionReply

class DiscussionTests(TestCase):
    def test_scope(self):
        U=get_user_model()
        teacher=U.objects.create_user("teacher")
        student=U.objects.create_user("student")
        other=U.objects.create_user("other")
        d=Department.objects.create(name="Test")
        date=timezone.localdate()
        t=Term.objects.create(name="Test",starts=date,ends=date)
        course=Course.objects.create(code="T",title="Test",department=d,term=t,instructor=teacher,published=True)
        Enrollment.objects.create(student=student,course=course)
        topic=Discussion.objects.create(course=course,title="Test",prompt="Question",author=teacher)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("discussion",args=[topic.pk])).status_code,404)
        self.client.force_login(student)
        self.assertEqual(self.client.post(reverse("discussion",args=[topic.pk]),{"body":"Reply"}).status_code,302)
        self.assertEqual(DiscussionReply.objects.get().author,student)
        self.assertEqual(self.client.post(reverse("discussions",args=[course.pk]),{"title":"Test","prompt":"Test"}).status_code,403)
