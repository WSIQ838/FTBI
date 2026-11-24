from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Department,Term,Course,Assignment,Submission
from .gradebook import GradeCategory,AssignmentWeight,current_grade

class WeightedGradeTests(TestCase):
    def test_weighted_grade(self):
        user=get_user_model().objects.create_user("student")
        teacher=get_user_model().objects.create_user("teacher")
        today=timezone.localdate()
        d=Department.objects.create(name="Test")
        t=Term.objects.create(name="Test",starts=today,ends=today)
        c=Course.objects.create(code="T",title="Test",department=d,term=t,instructor=teacher)
        for name,weight,score in [("Assignments",40,80),("Final",60,100)]:
            cat=GradeCategory.objects.create(course=c,name=name,weight=weight)
            a=Assignment.objects.create(course=c,title=name,instructions="Test",due=timezone.now()+timedelta(days=1))
            AssignmentWeight.objects.create(assignment=a,category=cat,points=100)
            Submission.objects.create(student=user,assignment=a,body="Test",grade=score)
        self.assertEqual(current_grade(c,user),Decimal("92.00"))
