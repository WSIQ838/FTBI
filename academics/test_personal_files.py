import hashlib
import json
import zipfile
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment,Assignment,Submission
from .registrar import StudentProfile
from .documents import PrivateDocument,DocumentVersion
from .attachments import SubmissionAttachment
from .assessment_policy import SubmissionRevision
from .personal_files import build_archive


class PersonalFileTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user("files-owner")
        self.other=get_user_model().objects.create_user("files-other")
        d=Department.objects.create(name="Files")
        p=Program.objects.create(name="Program",department=d)
        self.profile=StudentProfile.objects.create(user=self.user,program=p,student_number="FILES",admitted_on=timezone.localdate())
        t=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="F",title="Files",department=d,term=t,instructor=self.other,published=True)
        self.enrollment=Enrollment.objects.create(student=self.user,course=self.course)
        assignment=Assignment.objects.create(course=self.course,title="Assignment",due=timezone.now()+timedelta(days=1))
        self.submission=Submission.objects.create(student=self.user,assignment=assignment,body="Answer")
        self.doc=PrivateDocument.objects.create(owner=self.user,title="Record",kind="student")
        self.version=DocumentVersion.objects.create(document=self.doc,number=1,original_name="../../unsafe.txt",data=b"private bytes",size=13,sha256=hashlib.sha256(b"private bytes").hexdigest(),uploaded_by=self.user)
        self.client.force_login(self.user)

    def contents(self,user=None):
        file,count,size=build_archive(user or self.user)
        with file,zipfile.ZipFile(file) as archive:
            return {name:archive.read(name) for name in archive.namelist()}

    def test_owner_archive_preserves_bytes_and_safe_names_excludes_others(self):
        other=PrivateDocument.objects.create(owner=self.other,title="Other private record",kind="student")
        DocumentVersion.objects.create(document=other,number=1,original_name="secret.txt",data=b"OTHER SECRET",size=12,sha256=hashlib.sha256(b"OTHER SECRET").hexdigest(),uploaded_by=self.other)
        contents=self.contents()
        name=f"document/{self.version.pk}.bin"
        self.assertEqual(contents[name],b"private bytes")
        self.assertTrue(all(".." not in path for path in contents))
        manifest=json.loads(contents["manifest.json"])
        self.assertEqual(manifest["files"][0]["original_name"],"../../unsafe.txt")
        self.assertEqual(manifest["files"][0]["sha256"],self.version.sha256)
        self.assertNotIn(b"OTHER SECRET",b"".join(contents.values()))

    def test_coursework_files_and_revisions_follow_current_enrollment_access(self):
        SubmissionAttachment.objects.create(submission=self.submission,original_name="current.txt",data=b"CURRENT",size=7)
        SubmissionRevision.objects.create(submission=self.submission,body="Old",submitted_at=timezone.now(),attachment_name="old.txt",attachment_data=b"OLD")
        doc=PrivateDocument.objects.create(owner=self.user,title="Course file",kind="coursework",submission=self.submission)
        DocumentVersion.objects.create(document=doc,number=1,original_name="extra.txt",data=b"EXTRA",size=5,sha256=hashlib.sha256(b"EXTRA").hexdigest(),uploaded_by=self.user)
        contents=self.contents();self.assertEqual(len(contents),5)
        self.enrollment.active=False;self.enrollment.save()
        contents=self.contents();self.assertEqual(len(contents),2)
        self.assertNotIn(b"CURRENT",b"".join(contents.values()))
        self.assertNotIn(b"OLD",b"".join(contents.values()))

    def test_size_count_and_integrity_limits_fail_without_partial_archive(self):
        with patch("academics.personal_files.MAX_BYTES",1):
            with self.assertRaises(ValidationError): build_archive(self.user)
        with patch("academics.personal_files.MAX_FILES",0):
            with self.assertRaises(ValidationError): build_archive(self.user)
        DocumentVersion.objects.filter(pk=self.version.pk).update(data=b"TAMPERED")
        with self.assertRaises(ValidationError): build_archive(self.user)

    def test_post_required_private_response_and_rate_limit(self):
        url=reverse("personal_files")
        self.assertEqual(self.client.get(url).status_code,405)
        response=self.client.post(url)
        self.assertEqual(response.status_code,200)
        self.assertIn("private",response["Cache-Control"]);self.assertIn("no-store",response["Cache-Control"])
        payload=b"".join(response.streaming_content);self.assertTrue(response.closed)
        with zipfile.ZipFile(BytesIO(payload)) as archive: self.assertIn("manifest.json",archive.namelist())
        self.assertEqual(self.client.post(url).status_code,429)
        from django.test import Client
        csrf_client=Client(enforce_csrf_checks=True);csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url).status_code,403)
        self.client.logout();self.assertEqual(self.client.post(url).status_code,302)

    def test_revoked_credentials_are_excluded(self):
        from .operations import TranscriptRequest
        from .transcripts import IssuedTranscript
        from .credentials import CredentialArtifact,CredentialRevocation
        request=TranscriptRequest.objects.create(student=self.profile,destination="Synthetic")
        issued=IssuedTranscript.objects.create(request=request,issued_by=self.other,snapshot={})
        payload=b"synthetic PDF bytes"
        artifact=CredentialArtifact.objects.create(student=self.profile,kind="transcript",transcript=issued,snapshot={},pdf=payload,sha256=hashlib.sha256(payload).hexdigest(),issued_by=self.other,issued_at=timezone.now())
        self.assertIn(f"credential/{artifact.pk}.pdf",self.contents())
        CredentialRevocation.objects.create(credential=artifact,reason="Synthetic revocation",revoked_by=self.other)
        self.assertNotIn(f"credential/{artifact.pk}.pdf",self.contents())
