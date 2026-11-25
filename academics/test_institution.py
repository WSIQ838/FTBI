import csv
from io import StringIO,BytesIO
from unittest.mock import patch
from datetime import timedelta
from PIL import Image
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment,Lesson
from .registrar import StudentProfile
from .institution import InstitutionSettings,PortalPreference,ImportBatch
from .bulk_imports import HEADERS


class InstitutionTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.manager=users.create_user("manager",is_staff=True)
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        self.department=Department.objects.create(name="Department")
        self.program=Program.objects.create(name="Program",department=self.department)
        self.term=Term.objects.create(name="Term",starts=timezone.localdate(),ends=timezone.localdate())

    def preview(self,kind,rows):
        buffer=StringIO(); writer=csv.writer(buffer);writer.writerow(HEADERS[kind]);writer.writerows(rows)
        return self.client.post(reverse("import_preview",args=[kind]),{"file":SimpleUploadedFile("records.csv",buffer.getvalue().encode())})

    def test_student_import_preview_commit_replay_and_owner_scope(self):
        self.client.force_login(self.manager)
        row=[self.student.username,"S1",self.program.pk,timezone.localdate().isoformat(),"active"]
        self.assertEqual(self.preview("students",[row]).status_code,302)
        self.assertFalse(StudentProfile.objects.exists())
        batch=ImportBatch.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("import_detail",args=[batch.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse("import_commit",args=[batch.pk])).status_code,404)
        self.client.force_login(self.manager)
        for _ in range(2): self.assertEqual(self.client.post(reverse("import_commit",args=[batch.pk])).status_code,302)
        self.assertEqual(StudentProfile.objects.count(),1)
        self.assertEqual(StudentProfile.objects.get().status_history.get().actor,self.manager)

    def test_import_revalidates_all_rows_and_rejects_duplicates(self):
        self.client.force_login(self.manager)
        rows=[[self.student.username,"S1",self.program.pk,timezone.localdate().isoformat(),"active"],[self.other.username,"S2",self.program.pk,timezone.localdate().isoformat(),"active"]]
        self.assertEqual(self.preview("students",rows).status_code,302)
        batch=ImportBatch.objects.get()
        StudentProfile.objects.create(user=self.other,student_number="S2",program=self.program,admitted_on=timezone.localdate())
        self.assertEqual(self.client.post(reverse("import_commit",args=[batch.pk])).status_code,400)
        self.assertFalse(StudentProfile.objects.filter(user=self.student).exists())
        batch.refresh_from_db(); self.assertIsNone(batch.committed_at)
        self.assertContains(self.preview("students",[rows[0],rows[0]]),"Duplicate student number")

    def test_course_import_unpublished_and_expired_preview(self):
        self.client.force_login(self.manager)
        row=["NEW101","New course",self.department.pk,self.term.pk,"01",3,self.manager.username,"Synthetic syllabus"]
        self.assertEqual(self.preview("courses",[row]).status_code,302)
        batch=ImportBatch.objects.get()
        self.assertEqual(self.client.post(reverse("import_commit",args=[batch.pk])).status_code,302)
        self.assertFalse(Course.objects.get().published)
        row[0]="NEW102"
        self.preview("courses",[row]); batch=ImportBatch.objects.latest("pk")
        ImportBatch.objects.filter(pk=batch.pk).update(created=timezone.now()-timedelta(days=2))
        self.assertEqual(self.client.post(reverse("import_commit",args=[batch.pk])).status_code,400)
        self.assertEqual(Course.objects.count(),1)

    def test_branding_authorization_contrast_and_public_name(self):
        data={"name":"Demonstration College","short_name":"DEMO","accent":"#175b9a","header":"#142844"}
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("institution_settings"),data).status_code,403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse("institution_settings"),data).status_code,302)
        data["accent"]="#ffffff"
        self.assertContains(self.client.post(reverse("institution_settings"),data),"4.5:1")
        self.assertEqual(InstitutionSettings.objects.get().accent,"#175b9a")
        self.client.logout()
        self.assertContains(self.client.get(reverse("login")),"Demonstration College")

    @override_settings(FTBI_CLAMAV_HOST="synthetic-scanner")
    @patch("academics.attachment_views.scan_clean",return_value=True)
    def test_scanned_logo_reencoded_and_served_as_image(self,scan):
        InstitutionSettings.objects.create(name="College",short_name="C")
        self.client.force_login(self.manager)
        stream=BytesIO(); Image.new("RGB",(20,20),"blue").save(stream,format="PNG")
        self.assertEqual(self.client.post(reverse("upload_institution_logo"),{"file":SimpleUploadedFile("logo.png",stream.getvalue())}).status_code,302)
        scan.assert_called_once()
        self.client.logout(); response=self.client.get(reverse("institution_logo"))
        self.assertEqual(response["Content-Type"],"image/png")
        with Image.open(BytesIO(response.content)) as logo: self.assertEqual(logo.size,(20,20))

    def test_preferences_timezone_isolation_and_dashboard_controls(self):
        course=Course.objects.create(code="A",title="Visible course",department=self.department,term=self.term,instructor=self.manager,published=True)
        Enrollment.objects.create(student=self.student,course=course)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("preferences"),{"timezone":"America/Los_Angeles","course_order":"title"}).status_code,302)
        response=self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["display_timezone"],"America/Los_Angeles")
        self.assertNotContains(response,"My courses")
        self.assertEqual(timezone.get_current_timezone_name(),"UTC")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("dashboard")).context["display_timezone"],"UTC")
        self.assertFalse(PortalPreference.objects.filter(user=self.other).exists())

    def test_search_filters_preserve_course_scope(self):
        course=Course.objects.create(code="A",title="Allowed",department=self.department,term=self.term,instructor=self.manager,published=True)
        other=Course.objects.create(code="B",title="Private",department=self.department,term=self.term,instructor=self.manager,published=True)
        Enrollment.objects.create(student=self.student,course=course)
        Lesson.objects.create(course=course,title="Allowed lesson",body="Text")
        Lesson.objects.create(course=other,title="Private lesson",body="Text")
        self.client.force_login(self.student)
        response=self.client.get(reverse("search"),{"term":self.term.pk,"department":self.department.pk,"kind":"lessons"})
        self.assertContains(response,"Allowed lesson");self.assertNotContains(response,"Private lesson")
