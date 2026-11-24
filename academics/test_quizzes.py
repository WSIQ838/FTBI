from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Department,Term,Course,Enrollment
from .quizzes import Quiz,Question,Attempt
class QuizTests(TestCase):
    def test_access_and_scoring(self):
        U=get_user_model()
        student=U.objects.create_user("student")
        teacher=U.objects.create_user("teacher")
        other=U.objects.create_user("other")
        today=timezone.localdate()
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Test",starts=today,ends=today)
        c=Course.objects.create(code="T",title="Test",department=d,term=t,instructor=teacher,published=True)
        Enrollment.objects.create(student=student,course=c)
        q=Quiz.objects.create(course=c,title="Exam",published=True,closes=timezone.now()+timedelta(days=1))
        item=Question.objects.create(quiz=q,prompt="Test?",option_a="One",option_b="Two",option_c="Three",option_d="Four",correct="B")
        url=f"/quizzes/{q.pk}/"
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(student)
        self.assertEqual(self.client.post(url,{"q"+str(item.pk):"B"}).status_code,302)
        self.assertEqual(Attempt.objects.get().score,1)
        self.assertEqual(self.client.post(url,{"q"+str(item.pk):"A"}).status_code,403)
