from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment
from .registrar import StudentProfile
from .advising import AdvisorAssignment
from .student_records import AcademicStanding
from .student_support import AdvisorSlot,AdvisorBooking,SupportCase,SupportNote,SuccessPlan,StudentIntervention,AtRiskAlert,StudentAccommodation


class SupportTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        self.advisor=users.create_user("advisor",is_staff=True)
        self.unassigned=users.create_user("unassigned",is_staff=True)
        self.manager=users.create_user("manager",is_staff=True)
        permission=Permission.objects.get(content_type__app_label="academics",codename="view_advisorassignment")
        for user in [self.advisor,self.unassigned]: user.user_permissions.add(permission)
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label="academics",content_type__model="studentaccommodation"))
        department=Department.objects.create(name="Student support")
        program=Program.objects.create(name="Program",department=department)
        self.profile=StudentProfile.objects.create(user=self.student,program=program,student_number="S1",admitted_on=timezone.localdate())
        self.assignment=AdvisorAssignment.objects.create(student=self.profile,advisor=self.advisor)
        self.term=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="A",title="Course",department=department,term=self.term,instructor=self.advisor,published=True)
        Enrollment.objects.create(student=self.student,course=self.course)
        self.case=SupportCase.objects.create(student=self.profile,advisor=self.advisor,subject="Help with study",description="Synthetic support request",category="academic")

    def test_appointment_booking_overlap_cancellation_and_privacy(self):
        start=timezone.now()+timedelta(days=1)
        self.client.force_login(self.advisor)
        payload={"starts":start.isoformat(),"ends":(start+timedelta(hours=1)).isoformat(),"location":"Advisor office"}
        self.assertEqual(self.client.post(reverse("create_advisor_slot"),payload).status_code,302)
        self.assertContains(self.client.post(reverse("create_advisor_slot"),payload),"overlaps another")
        slot=AdvisorSlot.objects.get()
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("book_advisor_slot",args=[slot.pk])).status_code,302)
        self.assertEqual(self.client.post(reverse("book_advisor_slot",args=[slot.pk])).status_code,403)
        booking=AdvisorBooking.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("change_advisor_booking",args=[booking.pk]),{"status":"cancelled"}).status_code,404)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("change_advisor_booking",args=[booking.pk]),{"status":"completed"}).status_code,403)
        self.assertEqual(self.client.post(reverse("change_advisor_booking",args=[booking.pk]),{"status":"cancelled"}).status_code,302)
        self.assertEqual(self.client.post(reverse("book_advisor_slot",args=[slot.pk])).status_code,302)
        self.client.force_login(self.advisor)
        self.assertEqual(self.client.post(reverse("close_advisor_slot",args=[slot.pk])).status_code,302)
        self.assertFalse(AdvisorBooking.objects.filter(status="booked").exists())

    def test_private_notes_and_assignment_revocation(self):
        url=reverse("support_case",args=[self.case.pk])
        self.client.force_login(self.advisor)
        self.assertEqual(self.client.post(url,{"body":"Private advisor detail"}).status_code,302)
        self.assertEqual(self.client.post(url,{"body":"Shared advice","shared":"on"}).status_code,302)
        self.client.force_login(self.student)
        response=self.client.get(url)
        self.assertContains(response,"Shared advice"); self.assertNotContains(response,"Private advisor detail")
        self.client.post(url,{"body":"Student response","shared":""})
        self.assertTrue(SupportNote.objects.get(body="Student response").shared)
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assignment.active=False; self.assignment.save()
        self.client.force_login(self.advisor)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(reverse("support_case_status",args=[self.case.pk]),{"status":"resolved"}).status_code,404)

    def test_plan_snapshots_interventions_and_case_resolution(self):
        self.client.force_login(self.advisor)
        plan={"goals":"Finish coursework","actions":"Weekly study meeting","review_on":timezone.localdate().isoformat()}
        for _ in range(2): self.assertEqual(self.client.post(reverse("support_action",args=[self.case.pk,"plan"]),plan).status_code,302)
        self.assertEqual(SuccessPlan.objects.count(),2)
        action={"action":"Private support referral","follow_up":timezone.localdate().isoformat()}
        self.assertEqual(self.client.post(reverse("support_action",args=[self.case.pk,"intervention"]),action).status_code,302)
        intervention=StudentIntervention.objects.get()
        self.assertEqual(self.client.post(reverse("finish_intervention",args=[intervention.pk]),{"outcome":"Referral completed"}).status_code,302)
        self.assertEqual(self.client.post(reverse("finish_intervention",args=[intervention.pk]),{"outcome":"Overwrite"}).status_code,403)
        self.client.post(reverse("support_case_status",args=[self.case.pk]),{"status":"resolved"})
        self.client.force_login(self.student)
        response=self.client.get(reverse("support_case",args=[self.case.pk]))
        self.assertContains(response,"Finish coursework"); self.assertContains(response,"Resolved")
        self.assertNotContains(response,"Private support referral")
        self.assertEqual(self.client.post(reverse("support_case_status",args=[self.case.pk]),{"status":"open"}).status_code,404)

    def test_latest_standing_alert_is_deduplicated_and_private(self):
        record=AcademicStanding.objects.create(student=self.profile,term=self.term,gpa=1,status="probation",policy_snapshot={"approval":"Synthetic"},calculated_by=self.manager)
        self.client.force_login(self.advisor)
        for _ in range(2): self.client.post(reverse("flag_risk"))
        self.assertEqual(AtRiskAlert.objects.count(),1)
        alert=AtRiskAlert.objects.get()
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.post(reverse("acknowledge_risk",args=[alert.pk])).status_code,404)
        self.client.force_login(self.advisor)
        self.client.post(reverse("acknowledge_risk",args=[alert.pk])); alert.refresh_from_db(); self.assertIsNotNone(alert.acknowledged)
        AcademicStanding.objects.create(student=self.profile,term=self.term,gpa=3,status="good",policy_snapshot={},calculated_by=self.manager)
        self.client.post(reverse("flag_risk")); self.assertEqual(AtRiskAlert.objects.count(),1)
        self.profile.refresh_from_db(); self.assertFalse(self.profile.registration_hold)

    def test_accommodation_approval_limits_teacher_visibility(self):
        self.client.force_login(self.manager)
        payload={"student":self.profile.pk,"course":self.course.pk,"instructions":"Approved functional adjustment","starts":timezone.localdate().isoformat(),"ends":(timezone.localdate()+timedelta(days=30)).isoformat(),"approval_reference":"Synthetic policy approval"}
        self.assertEqual(self.client.post(reverse("draft_accommodation"),payload).status_code,302)
        record=StudentAccommodation.objects.get()
        self.client.force_login(self.advisor)
        self.assertNotContains(self.client.get(reverse("accommodations")),"Approved functional adjustment")
        self.client.force_login(self.manager)
        self.client.post(reverse("review_accommodation",args=[record.pk]),{"status":"approved"})
        self.client.force_login(self.advisor)
        self.assertContains(self.client.get(reverse("accommodations")),"Approved functional adjustment")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("accommodations")),"Approved functional adjustment")
        self.client.force_login(self.manager)
        self.client.post(reverse("review_accommodation",args=[record.pk]),{"status":"revoked"})
        self.client.force_login(self.advisor)
        self.assertNotContains(self.client.get(reverse("accommodations")),"Approved functional adjustment")
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("accommodations")),"Revoked")

    def test_case_creation_is_limited_to_assigned_advisor(self):
        payload={"subject":"New support","description":"Synthetic","category":"academic","assignment":self.assignment.pk}
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("create_support_case"),payload).status_code,302)
        self.client.force_login(self.advisor)
        self.assertEqual(self.client.post(reverse("create_advisee_case",args=[self.assignment.pk]),payload).status_code,302)
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.post(reverse("create_advisee_case",args=[self.assignment.pk]),payload).status_code,404)
