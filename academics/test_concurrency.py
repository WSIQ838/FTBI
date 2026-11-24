"""Row-lock behavior must be exercised on PostgreSQL, never inferred from SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from django.test import TransactionTestCase, Client, skipUnlessDBFeature
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone
from .models import Department,Term,Course,Enrollment
from .quizzes import Quiz,Question,Attempt


@skipUnlessDBFeature("has_select_for_update")
class ExaminationConcurrencyTests(TransactionTestCase):
    def test_duplicate_simultaneous_attempt_is_recorded_once(self):
        teacher=get_user_model().objects.create_user("teacher")
        student=get_user_model().objects.create_user("student")
        d=Department.objects.create(name="Concurrent")
        t=Term.objects.create(name="Fall",starts=timezone.localdate(),ends=timezone.localdate())
        c=Course.objects.create(code="C",title="Concurrency",department=d,term=t,instructor=teacher,published=True)
        Enrollment.objects.create(course=c,student=student)
        quiz=Quiz.objects.create(course=c,title="Quiz",published=True,closes=timezone.now()+timedelta(days=1))
        q=Question.objects.create(quiz=quiz,prompt="True?",kind="boolean",answer_key=[True])
        clients=[Client(),Client()]
        for client in clients: client.force_login(student)
        barrier=Barrier(2)
        def submit(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(f"/quizzes/{quiz.pk}/",{"attempt_number":"1",f"q{q.pk}":"true"}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes=list(executor.map(submit,clients))
        self.assertEqual(sorted(codes),[302,403])
        self.assertEqual(Attempt.objects.filter(quiz=quiz).count(),1)
