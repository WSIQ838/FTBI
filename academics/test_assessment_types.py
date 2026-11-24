from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Department,Term,Course,Enrollment
from .quizzes import Quiz,Question,Attempt
from .timing import QuizPolicy,QuizSession
from .exam_extensions import ExamAccommodation,BankQuestion
from .assessment_engine import attempt_grade


class AssessmentTypesTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.teacher=users.create_user("teacher")
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Fall",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="A",title="A",department=d,term=t,instructor=self.teacher,published=True)
        Enrollment.objects.create(student=self.student,course=self.course)
        self.quiz=Quiz.objects.create(course=self.course,title="Exam",closes=timezone.now()+timedelta(days=1),published=True,results_released=False)
        self.url=reverse("take_quiz",args=[self.quiz.pk])

    def question(self,kind,key,points=2):
        return Question.objects.create(quiz=self.quiz,prompt=kind,kind=kind,answer_key=key,points=points)

    def test_mixed_exam_scoring_manual_review_and_release(self):
        boolean=self.question("boolean",[True])
        short=self.question("short",["Paris"])
        blank=self.question("blank",["New York"])
        match=self.question("matching",{"France":"Paris","Italy":"Rome"},4)
        essay=self.question("essay",[],5)
        self.client.force_login(self.student)
        page=self.client.get(self.url)
        self.assertNotContains(page,'answer_key')
        self.assertEqual(self.client.post(self.url,{"attempt_number":"1"}).status_code,400)
        data={"attempt_number":"1",f"q{boolean.pk}":"true",f"q{short.pk}":" paris ",f"q{blank.pk}":"new   YORK",f"q{match.pk}_0":"Paris",f"q{match.pk}_1":"Paris",f"q{essay.pk}":"My essay"}
        self.assertEqual(self.client.post(self.url,data).status_code,302)
        attempt=Attempt.objects.get()
        self.assertEqual((attempt.score,attempt.total,attempt.graded),(8,15,False))
        self.assertContains(self.client.get(reverse("quizzes")),"Results withheld")
        grading=reverse("grade_attempt",args=[attempt.pk])
        self.assertEqual(self.client.get(grading).status_code,404)
        self.client.force_login(self.teacher)
        values={f"score_{a.pk}":str(a.earned if a.earned is not None else 4) for a in attempt.answers.all()}
        self.assertEqual(self.client.post(grading,values).status_code,302)
        attempt.refresh_from_db()
        self.assertEqual((attempt.score,attempt.graded),(12,True))
        self.assertIsNone(attempt_grade(self.quiz,self.student))
        self.quiz.results_released=True; self.quiz.save()
        self.assertEqual(attempt_grade(self.quiz,self.student),80)

    def test_pool_stable_accommodations_and_policy_lock(self):
        for i in range(5): self.question("boolean",[True])
        policy=QuizPolicy.objects.create(quiz=self.quiz,minutes=10,select_count=2,max_attempts=2)
        self.quiz.closes=timezone.now()-timedelta(minutes=1); self.quiz.save()
        ExamAccommodation.objects.create(quiz=self.quiz,student=self.student,extra_minutes=5,extended_close=timezone.now()+timedelta(hours=1))
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code,200)
        session=QuizSession.objects.get()
        self.assertEqual(len(session.question_ids),2)
        self.assertEqual(session.expires-session.started,timedelta(minutes=15))
        self.client.get(self.url)
        self.assertEqual(QuizSession.objects.get().question_ids,session.question_ids)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(reverse("exam_policy",args=[self.quiz.pk]),{"minutes":20}).status_code,403)

    def test_attempt_aggregation(self):
        self.quiz.results_released=True; self.quiz.save()
        policy=QuizPolicy.objects.create(quiz=self.quiz)
        Attempt.objects.create(quiz=self.quiz,student=self.student,number=1,score=9,total=10)
        Attempt.objects.create(quiz=self.quiz,student=self.student,number=2,score=1,total=2)
        for rule,expected in [("highest",90),("latest",50),("average",70)]:
            policy.attempt_rule=rule; policy.save()
            self.quiz.refresh_from_db()
            self.assertEqual(attempt_grade(self.quiz,self.student),Decimal(expected))

    def test_bank_and_question_authorization(self):
        bank=BankQuestion.objects.create(owner=self.other,prompt="Private bank",kind="boolean",answer_key=[True])
        self.quiz.published=False; self.quiz.save()
        self.client.force_login(self.teacher)
        url=reverse("bank_import",args=[self.quiz.pk])
        self.assertEqual(self.client.post(url,{"question":bank.pk}).status_code,404)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get(reverse("question",args=[self.quiz.pk,0])).status_code,404)

    def test_invalid_answer_keys_rejected_by_authoring(self):
        self.quiz.published=False; self.quiz.save()
        self.client.force_login(self.teacher)
        url=reverse("question",args=[self.quiz.pk,0])
        self.assertContains(self.client.post(url,{"kind":"boolean","prompt":"Question","points":2,"answer_key":"[]"}),"True/false requires")
        self.assertEqual(self.quiz.questions.count(),0)

    def test_legacy_attempt_cannot_be_erased_by_empty_regrade(self):
        attempt=Attempt.objects.create(quiz=self.quiz,student=self.student,score=5,total=10)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(reverse("grade_attempt",args=[attempt.pk]),{}).status_code,403)
        attempt.refresh_from_db(); self.assertEqual(attempt.score,5)
