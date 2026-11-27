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

    def appeal_fixture(self):
        self.appeal_policy=WithdrawalWindow.objects.create(course=self.course,opens=timezone.now()-timedelta(days=3),closes=timezone.now()-timedelta(days=1),appeal_days=7,appeal_approval_reference="SYNTHETIC POLICY")
        self.denial=WithdrawalRequest.objects.create(enrollment=self.enrollment,reason="Original request",status="denied",reviewed_by=self.registrar,reviewed_at=timezone.now())
        self.appeal_url=reverse("withdrawal_appeal",args=[self.denial.pk])
        self.reviewer=get_user_model().objects.create_user("appeal-reviewer",is_staff=True)
        self.reviewer.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        self.client.force_login(self.student)

    def test_appeal_grant_preserves_original_and_records_w_once(self):
        from .student_records import WithdrawalAppeal
        self.appeal_fixture()
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"New grounds"}).status_code,302)
        appeal=WithdrawalAppeal.objects.get()
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"Overwrite"}).status_code,200)
        appeal.refresh_from_db();self.assertEqual(appeal.reason,"New grounds")
        review=reverse("review_withdrawal_appeal",args=[appeal.pk])
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(review,{"decision":"granted","reason":"Independent review required"}).status_code,403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(review,{"decision":"granted","reason":"Grounds accepted"}).status_code,302)
        self.assertEqual(self.client.post(review,{"decision":"granted","reason":"Replay"}).status_code,403)
        appeal.refresh_from_db();self.denial.refresh_from_db();self.enrollment.refresh_from_db()
        self.assertEqual(appeal.original_decision["reviewed_by"],self.registrar.pk)
        self.assertEqual(appeal.original_decision["status"],"denied")
        self.assertEqual((appeal.status,self.denial.status,self.enrollment.active),("granted","approved",False))
        self.assertEqual(FinalGrade.objects.get().letter,"W")
        self.client.force_login(self.student)
        self.assertContains(self.client.get(self.appeal_url),"Grounds accepted")
        self.assertEqual(self.client.post(reverse("register",args=[self.window.pk])).status_code,403)

    def test_appeals_disabled_expired_and_unapproved_policy_are_blocked(self):
        self.appeal_fixture()
        self.appeal_policy.appeal_days=0;self.appeal_policy.save()
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"Appeal"}).status_code,403)
        self.appeal_policy.appeal_days=7;self.appeal_policy.appeal_approval_reference="";self.appeal_policy.save()
        with self.assertRaises(ValidationError): self.appeal_policy.full_clean()
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"Appeal"}).status_code,403)
        self.appeal_policy.appeal_approval_reference="TEST";self.appeal_policy.save()
        self.denial.reviewed_at=timezone.now()-timedelta(days=8);self.denial.save()
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"Appeal"}).status_code,403)

    def test_appeal_privacy_and_self_review_denied(self):
        from .student_records import WithdrawalAppeal
        self.appeal_fixture()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.appeal_url,{"reason":"Other student's request"}).status_code,404)
        self.client.force_login(self.student)
        self.client.post(self.appeal_url,{"reason":"Private grounds"})
        appeal=WithdrawalAppeal.objects.get()
        review=reverse("review_withdrawal_appeal",args=[appeal.pk])
        self.assertEqual(self.client.get(review).status_code,403)
        self.student.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        self.assertEqual(self.client.post(review,{"decision":"granted","reason":"Self review"}).status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.appeal_url).status_code,404)

    def test_appeal_cannot_overwrite_released_grade(self):
        from .student_records import WithdrawalAppeal
        self.appeal_fixture();self.client.post(self.appeal_url,{"reason":"Grounds"})
        appeal=WithdrawalAppeal.objects.get()
        FinalGrade.objects.create(student=self.profile,course=self.course,letter="A",quality_points=4,credits_earned=3,released=True)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse("review_withdrawal_appeal",args=[appeal.pk]),{"decision":"granted","reason":"Reviewed"}).status_code,403)
        appeal.refresh_from_db();self.denial.refresh_from_db();self.enrollment.refresh_from_db()
        self.assertEqual((appeal.status,self.denial.status,self.enrollment.active),("pending","denied",True))
        self.assertEqual(FinalGrade.objects.get().letter,"A")

    def test_denied_appeal_keeps_enrollment_and_requires_reason(self):
        from .student_records import WithdrawalAppeal
        self.appeal_fixture();self.client.post(self.appeal_url,{"reason":"Grounds"})
        appeal=WithdrawalAppeal.objects.get();url=reverse("review_withdrawal_appeal",args=[appeal.pk])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(url,{"decision":"denied","reason":""}).status_code,200)
        appeal.refresh_from_db();self.assertEqual(appeal.status,"pending")
        self.assertEqual(self.client.post(url,{"decision":"denied","reason":"Original decision upheld"}).status_code,302)
        self.enrollment.refresh_from_db();self.assertTrue(self.enrollment.active)
        self.assertFalse(FinalGrade.objects.exists())

    def test_enrollment_letter_template_is_snapshotted_and_private(self):
        from .credentials import CredentialTemplate
        template=CredentialTemplate.objects.create(kind="enrollment",heading="Enrollment confirmation",
            body="{recipient} is enrolled with {institution} in {program}.",footer="Reference {identifier}",
            enabled=True,approval_reference="Synthetic approval")
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("issue_enrollment_letter")).status_code,302)
        record=EnrollmentVerification.objects.get()
        captured=record.snapshot.copy()
        self.assertEqual(captured["template"]["approval_reference"],"Synthetic approval")
        self.assertEqual(captured["program"],self.program.name)
        template.heading="Changed heading";template.save()
        self.course.title="Changed course";self.course.save()
        record.refresh_from_db();self.assertEqual(record.snapshot,captured)
        url=reverse("enrollment_letter",args=[record.identifier])
        from io import BytesIO
        from pyhanko.pdf_utils.reader import PdfFileReader
        rendered=PdfFileReader(BytesIO(self.client.get(url).content))
        content=rendered.root["/Pages"]["/Kids"][0].get_object()["/Contents"].data
        self.assertIn(b"Enrollment confirmation",content)
        self.assertNotIn(b"Changed heading",content)
        self.assertNotIn(b"Changed course",content)
        self.client.force_login(self.other);self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.registrar);self.assertEqual(self.client.get(url).status_code,200)

    def test_enrollment_letter_rejects_invalid_enabled_template_before_issuance(self):
        from .credentials import CredentialTemplate
        template=CredentialTemplate.objects.create(kind="enrollment",heading="{recipient.__class__}",enabled=True,approval_reference="Synthetic")
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("issue_enrollment_letter")).status_code,400)
        self.assertFalse(EnrollmentVerification.objects.exists())
        template.heading="Enrollment";template.approval_reference="  ";template.save()
        self.assertEqual(self.client.post(reverse("issue_enrollment_letter")).status_code,400)
        self.assertFalse(EnrollmentVerification.objects.exists())
        template.enabled=False;template.save()
        self.assertEqual(self.client.post(reverse("issue_enrollment_letter")).status_code,302)
        self.assertEqual(EnrollmentVerification.objects.get().snapshot["template"]["heading"],"Enrollment verification")

    def test_enrollment_letter_paginates_without_truncation_and_supports_legacy_snapshot(self):
        from io import BytesIO
        from uuid import uuid4
        from pyhanko.pdf_utils.reader import PdfFileReader
        from .enrollment_letters import render_letter
        snapshot={"institution":"Synthetic College","name":"Synthetic Student","student_number":"S001",
                  "enrollments":[{"course__code":f"C{i}","course__title":"Long course title "*10+"ENDCOURSE",
                                  "course__term__name":"Synthetic Term"} for i in range(60)]}
        reader=PdfFileReader(BytesIO(render_letter(snapshot,uuid4(),timezone.now())))
        self.assertGreater(reader.root["/Pages"]["/Count"],2)
        def streams(node):
            if node["/Type"]=="/Page": return [node["/Contents"].data]
            return [data for child in node["/Kids"] for data in streams(child.get_object())]
        data=b"\n".join(streams(reader.root["/Pages"]))
        self.assertEqual(data.count(b"ENDCOURSE"),60)
        self.assertIn(b"Not digitally signed",data)
        self.assertIn(b"Enrollment verification",data)

    def test_enrollment_letter_audit_failure_rolls_back_issuance(self):
        from unittest.mock import patch
        self.client.force_login(self.student)
        with patch("academics.student_record_views.AuditEvent.objects.create",side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError): self.client.post(reverse("issue_enrollment_letter"))
        self.assertFalse(EnrollmentVerification.objects.exists())
