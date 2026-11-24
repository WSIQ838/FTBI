from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Department,Program,Term,Course,Enrollment
from .registrar import StudentProfile,RegistrationWindow
from .services import FinalGrade
from .student_records import WithdrawalWindow,WithdrawalRequest,GradingScale,StandingPolicy,AcademicStanding,EmergencyContact,EnrollmentVerification,standing_for
from .prerequisites import Prerequisite,prerequisites_met


class StudentRecordsTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        self.registrar=users.create_user("registrar",is_staff=True)
        self.registrar.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        self.department=Department.objects.create(name="Student records")
        self.program=Program.objects.create(name="Program",department=self.department)
        self.profile=StudentProfile.objects.create(user=self.student,program=self.program,student_number="S001",admitted_on=timezone.localdate())
        self.term=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate()+timedelta(days=90))
        self.course=Course.objects.create(code="A",title="Course",department=self.department,term=self.term,instructor=self.registrar,published=True)
        self.enrollment=Enrollment.objects.create(student=self.student,course=self.course)
        self.window=RegistrationWindow.objects.create(course=self.course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1))

    def test_withdrawal_separate_window_and_approval(self):
        WithdrawalWindow.objects.create(course=self.course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=5))
        self.client.force_login(self.student)
        url=reverse("request_withdrawal",args=[self.enrollment.pk])
        self.assertEqual(self.client.post(url,{"reason":"Schedule change"}).status_code,302)
        request=WithdrawalRequest.objects.get()
        decide=reverse("decide_withdrawal",args=[request.pk])
        self.assertEqual(self.client.post(decide,{"decision":"approved"}).status_code,403)
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(decide,{"decision":"approved"}).status_code,302)
        self.enrollment.refresh_from_db(); self.assertFalse(self.enrollment.active)
        grade=FinalGrade.objects.get(); self.assertEqual((grade.letter,grade.quality_points,grade.credits_earned),("W",None,0))
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("register",args=[self.window.pk])).status_code,403)

    def test_withdrawal_preserves_released_grade(self):
        request=WithdrawalRequest.objects.create(enrollment=self.enrollment,reason="Request")
        FinalGrade.objects.create(student=self.profile,course=self.course,letter="A",quality_points=4,credits_earned=3,released=True)
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(reverse("decide_withdrawal",args=[request.pk]),{"decision":"approved"}).status_code,403)
        self.assertEqual(FinalGrade.objects.get().letter,"A")

    def test_custom_scale_standing_and_policy_history(self):
        scale=GradingScale.objects.create(program=self.program,name="Local scale",active=True,approval_reference="TEST",entries=[{"minimum":80,"letter":"HIGH","points":4,"passing":True},{"minimum":0,"letter":"LOW","points":1,"passing":False}])
        scale.full_clean()
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(reverse("scaled_final_grade",args=[self.enrollment.pk]),{"score":75}).status_code,302)
        grade=FinalGrade.objects.get(); self.assertEqual(grade.letter,"LOW"); self.assertFalse(grade.released)
        self.client.post(reverse("release_final_grade",args=[grade.pk]))
        policy=StandingPolicy.objects.create(program=self.program,enabled=True,minimum_gpa=2,approval_reference="TEST")
        record=standing_for(self.profile,self.term,self.registrar)
        self.assertEqual((record.gpa,record.status),(Decimal(1),"probation"))
        policy.minimum_gpa=0; policy.save()
        next_record=standing_for(self.profile,self.term,self.registrar)
        self.assertEqual(next_record.status,"good")
        record.refresh_from_db(); self.assertEqual(record.policy_snapshot["minimum_gpa"],"2.00")

    def test_grouped_prerequisites_and_corequisite(self):
        Prerequisite.objects.create(course=self.course,required_code="P1",group="foundation")
        Prerequisite.objects.create(course=self.course,required_code="P2",group="foundation")
        self.assertFalse(prerequisites_met(self.profile,self.course))
        other_course=Course.objects.create(code="P2",title="Prereq",department=self.department,term=self.term,instructor=self.registrar)
        FinalGrade.objects.create(student=self.profile,course=other_course,letter="C",quality_points=2,credits_earned=3,released=True)
        self.assertTrue(prerequisites_met(self.profile,self.course))
        rule=Prerequisite.objects.create(course=self.course,required_code="CO",kind="corequisite")
        self.assertFalse(prerequisites_met(self.profile,self.course))
        coreq=Course.objects.create(code="CO",title="Coreq",department=self.department,term=self.term,instructor=self.registrar)
        Enrollment.objects.create(student=self.student,course=coreq)
        self.assertTrue(prerequisites_met(self.profile,self.course))

    def test_export_letters_and_status_history_are_private(self):
        EmergencyContact.objects.create(student=self.profile,name="Private contact",relationship="Family",phone="555-0100")
        self.profile.status="leave"; self.profile.save()
        self.assertEqual(list(self.profile.status_history.order_by("pk").values_list("current",flat=True)),["active","leave"])
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("personal_export")).json()["emergency_contacts"][0]["name"],"Private contact")
        self.assertEqual(self.client.post(reverse("issue_enrollment_letter")).status_code,302)
        letter=EnrollmentVerification.objects.get()
        url=reverse("enrollment_letter",args=[letter.identifier])
        self.assertTrue(self.client.get(url).content.startswith(b"%PDF"))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get(reverse("personal_export")).status_code,404)
