import hashlib
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from .documents import PrivateDocument,DocumentVersion,DocumentVerification,storage_used
from .file_retention import FileRetentionPolicy,FileRetentionBatch,DocumentPreservationHold,propose_batch,apply_batch
from .personal_files import build_archive


class FileRetentionTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.owner=users.create_user("retention-owner")
        self.author=users.create_user("retention-author",is_staff=True)
        self.reviewer=users.create_user("retention-reviewer",is_staff=True)
        permissions=Permission.objects.filter(content_type__app_label="academics",content_type__model__in=["fileretentionpolicy","fileretentionbatch","documentpreservationhold"])
        for user in [self.author,self.reviewer]: user.user_permissions.set(permissions)
        self.policy=FileRetentionPolicy.objects.create(kind="student",minimum_age_days=30,keep_versions=1,enabled=True,approval_reference="SYNTHETIC APPROVAL")
        self.document=PrivateDocument.objects.create(owner=self.owner,title="Synthetic document",kind="student")
        self.versions=[]
        for number in range(1,4):
            data=f"FILE{number}".encode()
            self.versions.append(DocumentVersion.objects.create(document=self.document,number=number,original_name=f"{number}.txt",data=data,size=len(data),sha256=hashlib.sha256(data).hexdigest(),uploaded_by=self.owner))
        DocumentVersion.objects.update(uploaded=timezone.now()-timedelta(days=100))

    def proposal(self): return propose_batch(self.policy,self.author,"Approved synthetic retention review")

    def test_independent_application_preserves_latest_metadata_and_frees_quota(self):
        batch=self.proposal()
        self.assertEqual([row["id"] for row in batch.rows],[self.versions[0].pk,self.versions[1].pk])
        self.assertEqual(storage_used(self.owner),15)
        with self.assertRaises(ValidationError): apply_batch(batch,self.author)
        self.assertEqual(apply_batch(batch,self.reviewer),2)
        first=DocumentVersion.objects.get(pk=self.versions[0].pk)
        self.assertEqual(bytes(first.data),b"");self.assertEqual(first.size,5);self.assertEqual(first.sha256,self.versions[0].sha256)
        self.assertIsNotNone(first.purged_at);self.assertEqual(storage_used(self.owner),5)
        self.assertEqual(bytes(DocumentVersion.objects.get(pk=self.versions[2].pk).data),b"FILE3")
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("document_download",args=[first.pk])).status_code,410)
        file,count,size=build_archive(self.owner);file.close();self.assertEqual((count,size),(1,5))

    def test_disabled_unapproved_or_unauthorized_retention_cannot_propose(self):
        self.policy.enabled=False;self.policy.save()
        with self.assertRaises(ValidationError): self.proposal()
        self.policy.enabled=True;self.policy.approval_reference="";self.policy.save()
        with self.assertRaises(ValidationError): self.proposal()
        self.policy.approval_reference="TEST";self.policy.save()
        with self.assertRaises(ValidationError): propose_batch(self.policy,self.owner,"Not authorized")
        with self.assertRaises(ValidationError): apply_batch(self.proposal(),self.owner)
        self.assertFalse(DocumentVersion.objects.filter(purged_at__isnull=False).exists())

    def test_current_reviewed_and_coursework_versions_are_protected(self):
        DocumentVerification.objects.create(version=self.versions[0],reviewer=self.reviewer,status="verified",note="Preserve reviewed evidence")
        DocumentVerification.objects.create(version=self.versions[1],reviewer=self.reviewer,status="rejected",note="Retain review history")
        with self.assertRaises(ValidationError): self.proposal()
        self.policy.kind="coursework"
        with self.assertRaises(ValidationError): self.policy.full_clean()

    def test_hold_blocks_pending_preview_and_release_keeps_history(self):
        batch=self.proposal();self.client.force_login(self.author)
        self.assertEqual(self.client.post(reverse("retention_hold"),{"document_id":self.document.pk,"reason":"Preserve for case TEST"}).status_code,302)
        hold=DocumentPreservationHold.objects.get()
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        with self.assertRaises(ValidationError): self.proposal()
        self.assertEqual(self.client.post(reverse("retention_release_hold",args=[hold.pk]),{"reason":"Approved case closure"}).status_code,302)
        hold.refresh_from_db();self.assertEqual(hold.reason,"Preserve for case TEST");self.assertEqual(hold.release_reason,"Approved case closure")
        self.assertEqual(len(self.proposal().rows),2)

    def test_policy_change_expiry_and_preview_tampering_require_new_review(self):
        batch=self.proposal()
        self.policy.keep_versions=2;self.policy.save()
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        self.policy.keep_versions=1;self.policy.save()
        FileRetentionBatch.objects.filter(pk=batch.pk).update(created=timezone.now()-timedelta(hours=25))
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        batch=self.proposal();FileRetentionBatch.objects.filter(pk=batch.pk).update(rows=[])
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        self.assertFalse(DocumentVersion.objects.filter(purged_at__isnull=False).exists())

    def test_integrity_failure_and_late_verification_leave_all_payloads_intact(self):
        batch=self.proposal()
        DocumentVersion.objects.filter(pk=self.versions[1].pk).update(data=b"TAMPER")
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        self.assertEqual(bytes(DocumentVersion.objects.get(pk=self.versions[0].pk).data),b"FILE1")
        DocumentVersion.objects.filter(pk=self.versions[1].pk).update(data=b"FILE2")
        DocumentVerification.objects.create(version=self.versions[1],reviewer=self.reviewer,status="verified",note="Reviewed after preview")
        with self.assertRaises(ValidationError): apply_batch(batch,self.reviewer)
        self.assertFalse(DocumentVersion.objects.filter(purged_at__isnull=False).exists())

    def test_portal_requires_role_and_explicit_confirmation(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("file_retention")).status_code,403)
        self.assertEqual(self.client.post(reverse("retention_hold"),{"document_id":self.document.pk,"reason":"No permission"}).status_code,403)
        batch=self.proposal();self.client.force_login(self.reviewer)
        url=reverse("retention_batch",args=[batch.pk])
        self.assertContains(self.client.get(url),"Backups and external copies are not erased")
        self.assertEqual(self.client.post(url,{}).status_code,200)
        self.assertFalse(DocumentVersion.objects.filter(purged_at__isnull=False).exists())
        self.assertEqual(self.client.post(url,{"confirm":"on"}).status_code,302)
        self.assertContains(self.client.get(url),"cannot be applied again")
