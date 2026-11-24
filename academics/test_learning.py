from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Department,Term,Course,Enrollment,Lesson,Assignment,Submission
from .learning import LearningModule,LessonCompletion,CompletionPolicy,CourseCertificate


class LearningTests(TestCase):
    def setUp(self):
        self.teacher=get_user_model().objects.create_user("teacher")
        self.student=get_user_model().objects.create_user("student")
        self.other=get_user_model().objects.create_user("other")
        d=Department.objects.create(name="Learning")
        t=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="L",title="Learning",department=d,term=t,instructor=self.teacher,published=True)
        Enrollment.objects.create(student=self.student,course=self.course)
        self.first=LearningModule.objects.create(course=self.course,title="First")
        self.second=LearningModule.objects.create(course=self.course,title="Second",position=2)
        self.second.prerequisites.add(self.first)
        self.a=Lesson.objects.create(course=self.course,module=self.first,title="Intro",body="Intro body")
        self.b=Lesson.objects.create(course=self.course,module=self.second,title="Advanced",body="Locked body",video_url="https://example.com/lesson.mp4")

    def test_prerequisites_hide_content_and_prevent_completion(self):
        self.client.force_login(self.student)
        page=reverse("course",args=[self.course.pk])
        self.assertNotContains(self.client.get(page),"Locked body")
        self.assertEqual(self.client.get(reverse("search"),{"q":"Advanced"}).context["lessons"],[])
        self.assertEqual(self.client.post(reverse("complete_lesson",args=[self.b.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse("complete_lesson",args=[self.a.pk])).status_code,302)
        self.assertContains(self.client.get(page),"Locked body")
        self.client.post(reverse("complete_lesson",args=[self.a.pk]))
        self.assertEqual(LessonCompletion.objects.count(),1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("complete_lesson",args=[self.a.pk])).status_code,404)

    def test_cycle_and_cross_course_module_rejected(self):
        self.client.force_login(self.teacher)
        url=reverse("module_editor",args=[self.course.pk,self.first.pk])
        self.assertContains(self.client.post(url,{"title":"First","position":1,"prerequisites":[self.second.pk]}),"cannot form a cycle")
        other=Course.objects.create(code="O",title="Other",department=self.course.department,term=self.course.term,instructor=self.teacher)
        module=LearningModule.objects.create(course=other,title="Other")
        self.assertEqual(self.client.post(reverse("author",args=[self.course.pk,"lesson",0]),{"title":"Bad","body":"Bad","position":1,"module":module.pk}).status_code,200)
        self.assertEqual(self.course.lessons.count(),2)

    def test_certificate_eligibility_privacy_and_snapshot(self):
        CompletionPolicy.objects.create(course=self.course,enabled=True,minimum_score=70)
        assignment=Assignment.objects.create(course=self.course,title="Work",instructions="Work",due=timezone.now()+timedelta(days=1))
        url=reverse("issue_course_certificate",args=[self.course.pk])
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(url).status_code,403)
        for lesson in (self.a,self.b): self.client.post(reverse("complete_lesson",args=[lesson.pk]))
        self.assertEqual(self.client.post(url).status_code,403)
        Submission.objects.create(assignment=assignment,student=self.student,body="Work",grade=80)
        self.assertEqual(self.client.post(url).status_code,302)
        certificate=CourseCertificate.objects.get()
        self.client.post(url); self.assertEqual(CourseCertificate.objects.count(),1)
        self.course.title="Changed"; self.course.save()
        certificate.refresh_from_db(); self.assertEqual(certificate.snapshot["course"],"Learning")
        pdf=reverse("course_certificate",args=[certificate.identifier])
        self.assertTrue(self.client.get(pdf).content.startswith(b"%PDF"))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(pdf).status_code,404)

    def test_video_scheme_and_module_structure_lock(self):
        self.client.force_login(self.teacher)
        url=reverse("author",args=[self.course.pk,"lesson",self.a.pk])
        response=self.client.post(url,{"title":"Intro","body":"Body","position":1,"video_url":"http://example.com/video"})
        self.assertContains(response,"must use HTTPS")
        LessonCompletion.objects.create(student=self.student,lesson=self.a)
        self.assertEqual(self.client.get(reverse("module_editor",args=[self.course.pk,self.first.pk])).status_code,403)
