from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Course,Department,Term,Lesson
class FacultyTests(TestCase):
    def test_scoped_authoring(self):
        U=get_user_model()
        instructor=U.objects.create_user("instructor")
        other=U.objects.create_user("other")
        today=timezone.localdate()
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Test",starts=today,ends=today)
        c=Course.objects.create(code="T",title="Test",department=d,term=t,instructor=instructor)
        url=reverse("author",args=[c.pk,"lesson",0])
        self.client.force_login(other)
        self.assertEqual(self.client.post(url,{"title":"Test","body":"Body","position":1}).status_code,404)
        self.client.force_login(instructor)
        self.assertEqual(self.client.post(url,{"title":"Test","body":"Body","position":1}).status_code,302)
        self.assertEqual(Lesson.objects.get().course,c)
