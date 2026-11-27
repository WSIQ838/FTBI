from datetime import timedelta
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Enrollment,Assignment,Submission,Lesson
from .learning import LearningModule


class PortalQueryTests(TestCase):
    def setUp(self):
        self.teacher=get_user_model().objects.create_user("query-teacher")
        self.student=get_user_model().objects.create_user("query-student")
        self.department=Department.objects.create(name="Synthetic query fixture")
        self.term=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="Q0",title="Course",department=self.department,term=self.term,instructor=self.teacher,published=True)
        Enrollment.objects.create(course=self.course,student=self.student)
        self.client.force_login(self.student)

    def queries(self,url):
        # Warm session/security bookkeeping before measuring the rendered request.
        self.client.get(url)
        with CaptureQueriesContext(connection) as captured:
            response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertNotIn('"academics_submissionattachment"."data"'," ".join(query["sql"] for query in captured))
        return len(captured),response

    def test_dashboard_queries_do_not_grow_per_course(self):
        small,_=self.queries(reverse("dashboard"))
        for index in range(1,31):
            course=Course.objects.create(code=f"Q{index}",title="Synthetic",department=self.department,term=self.term,instructor=self.teacher,published=True)
            Enrollment.objects.create(course=course,student=self.student)
        large,response=self.queries(reverse("dashboard"))
        self.assertContains(response,"Q30")
        self.assertLessEqual(large,small+1)

    def test_course_queries_do_not_grow_per_assignment_submission_or_same_module_lesson(self):
        module=LearningModule.objects.create(course=self.course,title="Module")
        def content(index):
            assignment=Assignment.objects.create(course=self.course,title=f"Assignment {index}",due=timezone.now()+timedelta(days=1))
            Submission.objects.create(assignment=assignment,student=self.student,body="Synthetic answer")
            Lesson.objects.create(course=self.course,module=module,title=f"Lesson {index}",body="Synthetic lesson")
        content(0)
        small,_=self.queries(reverse("course",args=[self.course.pk]))
        for index in range(1,31): content(index)
        large,response=self.queries(reverse("course",args=[self.course.pk]))
        self.assertContains(response,"Lesson 30");self.assertContains(response,"Assignment 30")
        self.assertLessEqual(large,small+1)
