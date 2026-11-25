import re
from datetime import timedelta
from django.test import TestCase,override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.core import mail
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment,Assignment,Submission
from .registrar import Application,StudentProfile
from .documents import PrivateDocument,DocumentVersion,DocumentVerification,StorageQuota,storage_used
from .admissions_support import ApplicantActivation,ApplicationReviewer,AdmissionInterview
from .public_admissions import token_generator


class AdmissionsDocumentsTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.applicant=users.create_user("applicant",email="applicant@example.invalid")
        self.other=users.create_user("other")
        self.reviewer=users.create_user("reviewer",is_staff=True)
        self.second=users.create_user("second",is_staff=True)
        self.manager=users.create_user("manager",is_staff=True)
        perms=Permission.objects.filter(content_type__app_label="academics")
        self.manager.user_permissions.set(perms)
        for user in [self.reviewer,self.second]: user.user_permissions.set(perms.filter(codename__in=["change_application","add_applicationnote","add_admissioninterview","change_admissioninterview","add_documentverification"]))
        self.department=Department.objects.create(name="Admissions")
        self.program=Program.objects.create(name="Program",department=self.department)
        self.application=Application.objects.create(applicant=self.applicant,program=self.program,statement="Synthetic application")
        cache.clear()

    def upload(self,kind,pk,body=b"Synthetic document"):
        return self.client.post(reverse("upload_document",args=[kind,pk]),{"title":"Evidence","file":SimpleUploadedFile("evidence.txt",body,content_type="text/plain")})

    def test_version_verification_and_private_download(self):
        self.client.force_login(self.applicant)
        self.assertEqual(self.upload("admission",self.application.pk).status_code,302)
        document=PrivateDocument.objects.get(); first=document.versions.get()
        self.client.force_login(self.other)
        for route,pk in [("document_detail",document.pk),("document_download",first.pk)]: self.assertEqual(self.client.get(reverse(route,args=[pk])).status_code,404)
        self.client.force_login(self.reviewer)
        response=self.client.post(reverse("verify_document",args=[first.pk]),{"status":"verified","note":"Matches reviewed source"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(reverse("verify_document",args=[first.pk]),{"status":"rejected","note":"Overwrite"}).status_code,403)
        self.client.force_login(self.applicant)
        self.assertEqual(self.upload("version",document.pk,b"Updated evidence").status_code,302)
        self.assertEqual(document.versions.count(),2)
        self.assertEqual(DocumentVerification.objects.count(),1)
        self.assertEqual(bytes(DocumentVersion.objects.get(pk=first.pk).data),b"Synthetic document")
        self.assertEqual(self.client.get(reverse("document_download",args=[first.pk])).content,b"Synthetic document")

    def test_storage_quota_counts_old_versions_and_rolls_back_rejection(self):
        StorageQuota.objects.create(user=self.applicant,limit_bytes=8)
        self.client.force_login(self.applicant)
        self.assertEqual(self.upload("admission",self.application.pk,b"12345").status_code,302)
        document=PrivateDocument.objects.get()
        response=self.upload("version",document.pk,b"6789")
        self.assertContains(response,"Storage quota exceeded")
        self.assertEqual(DocumentVersion.objects.count(),1)
        self.assertEqual(storage_used(self.applicant),5)

    def test_assigned_review_scope_notes_and_decisions(self):
        ApplicationReviewer.objects.create(application=self.application,reviewer=self.reviewer,assigned_by=self.manager)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse("application_note",args=[self.application.pk]),{"body":"Private reviewer note"}).status_code,302)
        self.assertContains(self.client.get(reverse("application_details",args=[self.application.pk])),"Private reviewer note")
        self.client.force_login(self.applicant)
        self.assertNotContains(self.client.get(reverse("application_details",args=[self.application.pk])),"Private reviewer note")
        self.client.force_login(self.second)
        self.assertEqual(self.client.get(reverse("application_details",args=[self.application.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse("admission_decide",args=[self.application.pk]),{"decision":"accepted"}).status_code,403)
        self.assertNotContains(self.client.get(reverse("admission_review")),"Synthetic application")

    def test_interview_overlap_and_cancel(self):
        self.client.force_login(self.reviewer)
        start=timezone.now()+timedelta(days=1)
        data={"interviewer":self.reviewer.pk,"starts":start.isoformat(),"ends":(start+timedelta(hours=1)).isoformat(),"location":"Admissions office"}
        route=reverse("schedule_interview",args=[self.application.pk])
        self.assertEqual(self.client.post(route,data).status_code,302)
        self.assertContains(self.client.post(route,data),"overlapping interview")
        item=AdmissionInterview.objects.get()
        self.client.force_login(self.applicant)
        self.assertContains(self.client.get(reverse("application_details",args=[self.application.pk])),"Admissions office")
        self.assertEqual(self.client.post(reverse("cancel_interview",args=[item.pk])).status_code,403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse("cancel_interview",args=[item.pk])).status_code,302)
        self.assertEqual(self.client.post(route,data).status_code,302)

    def test_multiple_coursework_files_lock_after_grading(self):
        term=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())
        course=Course.objects.create(code="A",title="Course",department=self.department,term=term,instructor=self.reviewer,published=True)
        Enrollment.objects.create(student=self.applicant,course=course)
        assignment=Assignment.objects.create(course=course,title="Work",instructions="Work",due=timezone.now()+timedelta(days=1))
        submission=Submission.objects.create(assignment=assignment,student=self.applicant,body="Work")
        self.client.force_login(self.applicant)
        for body in [b"first",b"second"]: self.assertEqual(self.upload("coursework",submission.pk,body).status_code,302)
        self.assertEqual(PrivateDocument.objects.count(),2)
        submission.grade=90; submission.save()
        self.assertEqual(self.upload("coursework",submission.pk,b"third").status_code,403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(reverse("document_download",args=[DocumentVersion.objects.first().pk])).status_code,200)

    def test_institution_library_requires_publication_and_export_permissions(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.upload("institution",0).status_code,302)
        document=PrivateDocument.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("document_detail",args=[document.pk])).status_code,404)
        document.published=True; document.save()
        self.assertEqual(self.client.get(reverse("document_detail",args=[document.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse("admission_conversion_report")).status_code,403)
        self.client.force_login(self.manager)
        StudentProfile.objects.create(user=self.applicant,program=self.program,student_number="S01",admitted_on=timezone.localdate())
        self.assertContains(self.client.get(reverse("admission_conversion_report")),"True")

    @override_settings(FTBI_PUBLIC_ADMISSIONS=True,SMTP_CONFIGURED=True,FTBI_ADMISSIONS_ORIGIN="https://college.example",EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_activation_recovery_rotates_token_and_cannot_reactivate_disabled_accounts(self):
        self.applicant.is_active=False; self.applicant.save()
        ApplicantActivation.objects.create(user=self.applicant)
        old=reverse("applicant_activate",args=[self.applicant.pk,token_generator.make_token(self.applicant)])
        data={"username":self.applicant.username,"email":self.applicant.email}
        self.assertEqual(self.client.post(reverse("resend_activation"),data).status_code,200)
        self.assertEqual(self.client.get(old).status_code,404)
        url=re.search(r"https://college.example(/apply/activate/[^ ]+)",mail.outbox[-1].body).group(1)
        self.assertEqual(self.client.post(url).status_code,302)
        self.applicant.refresh_from_db(); self.applicant.is_active=False; self.applicant.save()
        before=len(mail.outbox)
        self.client.post(reverse("resend_activation"),data)
        self.assertEqual(len(mail.outbox),before)
        self.other.is_active=False; self.other.save()
        unregistered=reverse("applicant_activate",args=[self.other.pk,token_generator.make_token(self.other)])
        self.assertEqual(self.client.post(unregistered).status_code,404)
