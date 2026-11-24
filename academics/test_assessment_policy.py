from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Department, Term, Course, Assignment, Enrollment, Submission
from .assessment_policy import AssignmentPolicy, RubricCriterion
from .attachments import SubmissionAttachment
from .gradebook import GradeCategory, AssignmentWeight
from .quizzes import Quiz, Question
from .timing import QuizPolicy


class AssignmentPolicyTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.teacher = users.create_user("teacher")
        self.student = users.create_user("student")
        self.other = users.create_user("other")
        department = Department.objects.create(name="Academic")
        term = Term.objects.create(name="Fall", starts=timezone.localdate(), ends=timezone.localdate())
        self.course = Course.objects.create(code="A", title="A", department=department, term=term, instructor=self.teacher, published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assignment = Assignment.objects.create(course=self.course, title="Essay", instructions="Write", due=timezone.now()+timedelta(days=1))
        self.url = reverse("submit", args=[self.assignment.pk])

    def test_resubmission_preserves_grade_text_and_attachment(self):
        AssignmentPolicy.objects.create(assignment=self.assignment, max_submissions=2, allow_graded_resubmission=True)
        old = Submission.objects.create(assignment=self.assignment, student=self.student, body="First", grade=60, feedback="Revise")
        SubmissionAttachment.objects.create(submission=old, original_name="first.txt", data=b"first", size=5)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, {"body": "Second"}).status_code, 302)
        old.refresh_from_db()
        self.assertEqual(old.body, "Second")
        self.assertIsNone(old.grade)
        revision = old.revisions.get()
        self.assertEqual((revision.body, revision.grade, bytes(revision.attachment_data)), ("First", 60, b"first"))
        self.assertFalse(SubmissionAttachment.objects.filter(submission=old).exists())
        self.assertEqual(self.client.post(self.url, {"body": "Third"}).status_code, 403)
        history = reverse("submission_history", args=[old.pk])
        self.assertContains(self.client.get(history), "First")
        archive = reverse("revision_attachment", args=[revision.pk])
        self.assertEqual(self.client.get(archive).content, b"first")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(history).status_code, 404)
        self.assertEqual(self.client.get(archive).status_code, 404)

    def test_graded_default_closed_and_invalid_post_does_not_archive(self):
        old = Submission.objects.create(assignment=self.assignment, student=self.student, body="First", grade=60)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, {"body": "Second"}).status_code, 403)
        old.grade = None
        old.save()
        self.assertEqual(self.client.post(self.url, {"body": ""}).status_code, 200)
        self.assertEqual(old.revisions.count(), 0)

    def test_late_policy_and_scope(self):
        self.assignment.due = timezone.now()-timedelta(hours=1)
        self.assignment.save()
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, {"body": "Late"}).status_code, 403)
        AssignmentPolicy.objects.create(assignment=self.assignment, late_hours=2)
        self.assertEqual(self.client.post(self.url, {"body": "Late"}).status_code, 302)
        self.assertEqual(self.client.get(reverse("assignment_policy", args=[self.assignment.pk])).status_code, 404)

    def test_rubric_percentage_validation_and_lock(self):
        c1 = RubricCriterion.objects.create(assignment=self.assignment, title="Evidence", points=3)
        c2 = RubricCriterion.objects.create(assignment=self.assignment, title="Clarity", points=1)
        s = Submission.objects.create(assignment=self.assignment, student=self.student, body="Work")
        self.client.force_login(self.teacher)
        url = reverse("grade", args=[s.pk])
        self.assertEqual(self.client.post(url, {f"criterion_{c1.pk}": 4, f"criterion_{c2.pk}": 1}).status_code, 200)
        s.refresh_from_db()
        self.assertIsNone(s.grade)
        self.assertEqual(self.client.post(url, {f"criterion_{c1.pk}": 2, f"criterion_{c2.pk}": 1, "grade": 100}).status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.grade, Decimal("75.00"))
        self.assertEqual(self.client.get(reverse("rubric", args=[self.assignment.pk])).status_code, 403)

    def test_complete_copy_isolated_from_student_records(self):
        AssignmentPolicy.objects.create(assignment=self.assignment, max_submissions=3)
        RubricCriterion.objects.create(assignment=self.assignment, title="Quality", points=10)
        category = GradeCategory.objects.create(course=self.course, name="Work", weight=100)
        AssignmentWeight.objects.create(assignment=self.assignment, category=category, points=50)
        quiz = Quiz.objects.create(course=self.course, title="Exam", closes=self.assignment.due, published=True)
        Question.objects.create(quiz=quiz, prompt="Q?", option_a="A", option_b="B", option_c="C", option_d="D", correct="B")
        QuizPolicy.objects.create(quiz=quiz, minutes=25)
        Submission.objects.create(assignment=self.assignment, student=self.student, body="Private")
        target = Course.objects.create(code="B", title="B", department=self.course.department, term=self.course.term, instructor=self.teacher)
        self.client.force_login(self.teacher)
        url = reverse("copy_content", args=[target.pk])
        self.assertEqual(self.client.post(url, {"source": self.course.pk, "shift_days": 7}).status_code, 302)
        copied = target.assignments.get()
        self.assertEqual(copied.due, self.assignment.due+timedelta(days=7))
        self.assertEqual(copied.policy.max_submissions, 3)
        self.assertEqual(copied.rubric.count(), 1)
        self.assertEqual(copied.assignmentweight.category.course_id, target.pk)
        self.assertEqual(copied.submissions.count(), 0)
        self.assertFalse(target.quiz_set.get().published)
        self.assertEqual(target.quiz_set.get().policy.minutes, 25)
        self.assertEqual(self.client.post(url, {"source": self.course.pk, "shift_days": 7}).status_code, 403)
