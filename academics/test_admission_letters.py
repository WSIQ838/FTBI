from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from .models import Department,Program
from .registrar import Application
from .credentials import CredentialTemplate
from .operations import AuditEvent
from .notification_models import DurableNotification


class AdmissionLetterTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.applicant=users.create_user("letter-applicant",first_name="Original",last_name="Applicant")
        self.other=users.create_user("letter-outsider")
        self.reviewer=users.create_user("letter-reviewer")
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label="academics",codename="change_application"))
        department=Department.objects.create(name="Synthetic department")
        self.program=Program.objects.create(department=department,name="Original Program")
        self.application=Application.objects.create(applicant=self.applicant,program=self.program,statement="Synthetic")
        self.decide=reverse("admission_decide",args=[self.application.pk])
        self.letter=reverse("decision_letter",args=[self.application.pk])
        self.client.force_login(self.reviewer)

    def test_approved_text_is_preserved_and_escaped_with_private_access(self):
        template=CredentialTemplate.objects.create(kind="acceptance",heading="Welcome {recipient}",body="Accepted to {program}. <script>alert(1)</script>",
            footer="Reference {identifier}",enabled=True,approval_reference="SYNTHETIC POLICY")
        self.assertEqual(self.client.post(self.decide,{"decision":"accepted"}).status_code,302)
        self.application.refresh_from_db();snapshot=self.application.decision_snapshot.copy()
        self.assertEqual(snapshot["template"]["approval_reference"],"SYNTHETIC POLICY")
        template.body="Changed wording";template.save()
        self.program.name="Changed Program";self.program.save()
        self.applicant.first_name="Changed";self.applicant.save()
        self.assertEqual(self.client.post(self.decide,{"decision":"rejected"}).status_code,403)
        self.application.refresh_from_db();self.assertEqual(self.application.decision_snapshot,snapshot)
        self.assertEqual(self.client.get(self.letter).status_code,404)
        self.client.force_login(self.applicant);response=self.client.get(self.letter)
        self.assertContains(response,"Welcome Original Applicant")
        self.assertContains(response,"Accepted to Original Program")
        self.assertContains(response,"&lt;script&gt;")
        self.assertNotContains(response,"<script>alert(1)</script>")
        self.assertNotContains(response,"Changed wording")
        self.client.force_login(self.other);self.assertEqual(self.client.get(self.letter).status_code,404)

    def test_invalid_template_blocks_decision_audit_and_notification(self):
        CredentialTemplate.objects.create(kind="acceptance",heading="{recipient.__class__}",enabled=True,approval_reference="SYNTHETIC")
        self.assertEqual(self.client.post(self.decide,{"decision":"accepted"}).status_code,400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status,"pending");self.assertEqual(self.application.decision_snapshot,{})
        self.assertFalse(AuditEvent.objects.filter(action="admission_accepted").exists())
        self.assertFalse(DurableNotification.objects.exists())

    def test_notification_failure_rolls_back_decision_and_captured_text(self):
        with patch("academics.admission_review.notify",side_effect=RuntimeError("Synthetic queue failure")):
            with self.assertRaises(RuntimeError): self.client.post(self.decide,{"decision":"accepted"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status,"pending");self.assertEqual(self.application.decision_snapshot,{})
        self.assertFalse(AuditEvent.objects.filter(action="admission_accepted").exists())

    def test_rejection_template_is_separate_and_admin_preserves_decided_record(self):
        from django.contrib import admin
        from .admin import ApplicationAdmin
        CredentialTemplate.objects.create(kind="acceptance",heading="Wrong heading",enabled=True,approval_reference="SYNTHETIC")
        CredentialTemplate.objects.create(kind="rejection",heading="Decision for {recipient}",body="Please contact admissions about other options.",enabled=True,approval_reference="SYNTHETIC")
        stale=Application.objects.get(pk=self.application.pk)
        self.assertEqual(self.client.post(self.decide,{"decision":"rejected"}).status_code,302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.decision_snapshot["status"],"rejected")
        self.client.force_login(self.applicant)
        self.assertContains(self.client.get(self.letter),"Decision: rejected")
        self.assertNotContains(self.client.get(self.letter),"Wrong heading")
        configured=ApplicationAdmin(Application,admin.site)
        for field in ["status","applicant","program","decision_snapshot"]:
            self.assertIn(field,configured.get_readonly_fields(None,self.application))
        self.assertFalse(configured.has_delete_permission(None,self.application))
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied): configured.save_model(None,stale,None,True)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status,"rejected")
        self.assertEqual(self.application.decision_snapshot["status"],"rejected")

    def test_legacy_and_disabled_template_use_standard_wording_without_backfill(self):
        CredentialTemplate.objects.create(kind="acceptance",heading="Disabled custom heading",enabled=False,approval_reference="SYNTHETIC")
        self.assertEqual(self.client.post(self.decide,{"decision":"accepted"}).status_code,302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.decision_snapshot["text"]["heading"],"Admissions decision")
        Application.objects.filter(pk=self.application.pk).update(decision_snapshot={})
        self.client.force_login(self.applicant)
        response=self.client.get(self.letter)
        self.assertContains(response,"This historical letter uses current account and program information")
        self.assertContains(response,"has been accepted")
        self.application.refresh_from_db();self.assertEqual(self.application.decision_snapshot,{})
