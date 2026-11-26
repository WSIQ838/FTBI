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
from .services import Announcement,CalendarEvent
from .discussions import Discussion,DiscussionReply


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


    def test_v2_communication_content_is_draft_shifted_and_excludes_student_replies(self):
        Announcement.objects.create(course=self.source,title="Course announcement",body="Authored notice",published=True)
        Announcement.objects.create(course=None,title="Institution-only notice",body="Not part of this course",published=True)
        starts=timezone.now()+timedelta(days=2)
        CalendarEvent.objects.create(course=self.source,title="Course meeting",starts=starts,ends=starts+timedelta(hours=1),published=True)
        topic=Discussion.objects.create(course=self.source,author=self.teacher,title="Instructor prompt",prompt="Discuss the reading")
        DiscussionReply.objects.create(discussion=topic,author=self.other,body="PRIVATE STUDENT REPLY")
        Discussion.objects.create(course=self.source,author=self.other,title="PRIVATE STUDENT TOPIC",prompt="Private")
        package=self.client.get(reverse("export_course_package",args=[self.source.pk])).json()
        self.assertEqual(package["version"],2)
        self.assertNotIn("PRIVATE",json.dumps(package));self.assertNotIn("Institution-only",json.dumps(package))
        response=self.client.post(reverse("import_course_package",args=[self.target.pk]),{"file":SimpleUploadedFile("course.json",json.dumps(package).encode()),"shift_days":7})
        self.assertEqual(response.status_code,302)
        self.assertFalse(Announcement.objects.get(course=self.target).published)
        event=CalendarEvent.objects.get(course=self.target)
        self.assertFalse(event.published);self.assertAlmostEqual((event.starts-starts).total_seconds(),7*86400,delta=0.001)
        copied=self.target.discussions.get()
        self.assertTrue(copied.closed);self.assertEqual(copied.author,self.teacher);self.assertFalse(copied.replies.exists())
        self.assertEqual(self.client.post(reverse("copy_content",args=[self.target.pk]),{"source":self.source.pk,"shift_days":0}).status_code,403)

    def test_v1_remains_supported_and_timezone_less_dates_are_rejected(self):
        self.package["version"]=1
        for key in ["announcements","calendar_events","discussion_prompts"]: self.package.pop(key)
        original=self.package["assignments"][0]["due"]
        self.package["assignments"][0]["due"]="2026-11-25T12:00:00"
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.assertFalse(self.target.lessons.exists())
        self.package["assignments"][0]["due"]=original
        self.assertEqual(self.upload(self.package).status_code,302)

    def test_late_calendar_failure_rolls_back_all_package_content(self):
        self.package["announcements"]=[{"title":"Draft","body":"Notice"}]
        self.package["calendar_events"]=[{"title":"Invalid interval","starts":"2026-11-25T12:00:00Z","ends":"2026-11-25T11:00:00Z"}]
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.assertFalse(Announcement.objects.filter(course=self.target).exists())
        self.assertFalse(self.target.quiz_set.exists());self.assertFalse(self.target.modules.exists())

    def test_existing_course_communication_blocks_import_and_copy(self):
        Announcement.objects.create(course=self.target,title="Retain existing",body="Do not overwrite")
        self.assertContains(self.upload(self.package),"Nothing was imported")
        self.assertFalse(self.target.lessons.exists())
        self.assertEqual(self.client.post(reverse("copy_content",args=[self.target.pk]),{"source":self.source.pk,"shift_days":0}).status_code,403)
        self.assertEqual(Announcement.objects.get(course=self.target).title,"Retain existing")

    def test_shift_overflow_returns_validation_error_and_rolls_back(self):
        self.package["assignments"][0]["due"]="9999-12-31T12:00:00Z"
        response=self.client.post(reverse("import_course_package",args=[self.target.pk]),{"file":SimpleUploadedFile("course.json",json.dumps(self.package).encode()),"shift_days":1})
        self.assertContains(response,"Nothing was imported")
        self.assertFalse(self.target.modules.exists());self.assertFalse(self.target.lessons.exists())
