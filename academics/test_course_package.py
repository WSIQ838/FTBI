import json
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Lesson,Assignment
from .learning import LearningModule,CompletionPolicy
from .assessment_policy import RubricCriterion,AssignmentPolicy
from .quizzes import Quiz,Question


class CoursePackageTests(TestCase):
    def setUp(self):
        self.teacher=get_user_model().objects.create_user("teacher")
        self.other=get_user_model().objects.create_user("other")
        d=Department.objects.create(name="Package")
        t=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        self.source=Course.objects.create(code="S",title="Source",department=d,term=t,instructor=self.teacher,syllabus="Syllabus")
        self.target=Course.objects.create(code="T",title="Target",department=d,term=t,instructor=self.teacher)
        module=LearningModule.objects.create(course=self.source,title="Module")
        Lesson.objects.create(course=self.source,module=module,title="Lesson",body="Body",video_url="https://example.com/video")
        a=Assignment.objects.create(course=self.source,title="Assignment",instructions="Instructions",due=timezone.now()+timedelta(days=1))
        RubricCriterion.objects.create(assignment=a,title="Criterion",points=10)
        AssignmentPolicy.objects.create(assignment=a,max_submissions=3)
        q=Quiz.objects.create(course=self.source,title="Quiz",closes=a.due,published=True)
        Question.objects.create(quiz=q,kind="short",prompt="Capital?",answer_key=["Paris"])
        CompletionPolicy.objects.create(course=self.source,enabled=True)
        self.client.force_login(self.teacher)
        self.package=self.client.get(reverse("export_course_package",args=[self.source.pk])).json()

    def upload(self,data):
        return self.client.post(reverse("import_course_package",args=[self.target.pk]),{"file":SimpleUploadedFile("course.json",json.dumps(data).encode())})

    def test_roundtrip_preserves_authored_content_without_publication(self):
        self.assertEqual(self.upload(self.package).status_code,302)
        self.assertEqual(self.target.lessons.get().module.title,"Module")
        self.assertEqual(self.target.lessons.get().video_url,"https://example.com/video")
        self.assertEqual(self.target.assignments.get().rubric.get().points,10)
        self.assertEqual(self.target.assignments.get().policy.max_submissions,3)
        self.assertEqual(self.target.quiz_set.get().questions.get().answer_key,["Paris"])
        self.assertFalse(self.target.quiz_set.get().published)
        self.assertFalse(self.target.completion_policy.enabled)
        self.assertEqual(self.target.enrollments.count(),0)

    def test_invalid_nested_package_rolls_back_everything(self):
        self.package["quizzes"][0]["questions"][0]["points"]=-1
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.assertEqual(self.target.lessons.count(),0)
        self.assertEqual(self.target.assignments.count(),0)
        self.assertEqual(self.target.modules.count(),0)

    def test_cycles_and_unknown_fields_rejected(self):
        self.package["modules"][0]["prerequisites"]=[0]
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.package["modules"][0]["prerequisites"]=[]
        self.package["students"]=[{"username":"injected"}]
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.assertEqual(self.target.modules.count(),0)

    def test_export_and_import_are_instructor_scoped(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("export_course_package",args=[self.source.pk])).status_code,404)
        self.assertEqual(self.upload(self.package).status_code,404)
