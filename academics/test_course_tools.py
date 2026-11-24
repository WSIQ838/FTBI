from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Lesson,Assignment,Enrollment
from .services import CalendarEvent
class CourseToolsTests(TestCase):
    def test_copy_and_calendar_scope(self):
        U=get_user_model()
        teacher=U.objects.create_user("teacher")
        student=U.objects.create_user("student")
        d=Department.objects.create(name="Test")
        today=timezone.localdate()
        t=Term.objects.create(name="Test",starts=today,ends=today)
        source=Course.objects.create(code="T1",title="Source",department=d,term=t,instructor=teacher,published=True)
        target=Course.objects.create(code="T2",title="Target",department=d,term=t,instructor=teacher)
        Lesson.objects.create(course=source,title="Lesson",body="Test")
        Assignment.objects.create(course=source,title="Assignment",instructions="Test",due=timezone.now())
        self.client.force_login(student)
        self.assertEqual(self.client.post(reverse("copy_content",args=[target.pk]),{"source":source.pk,"shift_days":7}).status_code,404)
        self.client.force_login(teacher)
        self.assertEqual(self.client.post(reverse("copy_content",args=[target.pk]),{"source":source.pk,"shift_days":7}).status_code,302)
        self.assertEqual(target.lessons.count(),1)
        self.assertEqual(target.assignments.count(),1)
        Enrollment.objects.create(student=student,course=source)
        for course,title in [(source,"Visible"),(target,"Hidden")]:
            CalendarEvent.objects.create(course=course,title=title,starts=timezone.now(),ends=timezone.now()+timedelta(hours=1),published=True)
        self.client.force_login(student)
        result=self.client.get(reverse("calendar_export"))
        self.assertContains(result,"SUMMARY:Visible")
        self.assertNotContains(result,"SUMMARY:Hidden")
