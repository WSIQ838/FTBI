from datetime import timedelta
from io import StringIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission,Group
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program,Term,Course,Enrollment
from .registrar import StudentProfile,Application
from .services import FinalGrade
from .institutional_reporting import Campus,DeanAssignment,InstitutionalReport,ReportSnapshot,ReportReview,execute_report,capture_report,review_snapshot,snapshot_access


class InstitutionalReportingTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.president=users.create_user("president",is_staff=True)
        self.dean=users.create_user("dean",is_staff=True)
        self.reviewer=users.create_user("reviewer",is_staff=True)
        call_command("setup_roles",verbosity=0,stdout=StringIO())
        for user,name in [(self.president,"President"),(self.dean,"Dean"),(self.reviewer,"Report Reviewer")]: user.groups.add(Group.objects.get(name=name))
        self.departments=[Department.objects.create(name="Department A"),Department.objects.create(name="Department B")]
        self.campuses=[Campus.objects.create(code="N",name="North"),Campus.objects.create(code="S",name="South")]
        self.term=Term.objects.create(name="Term",starts=timezone.localdate()-timedelta(days=90),ends=timezone.localdate())
        self.profiles=[];self.courses=[]
        for index in range(2):
            user=users.create_user(f"student{index}")
            program=Program.objects.create(name=f"Program {index}",department=self.departments[index])
            profile=StudentProfile.objects.create(user=user,program=program,campus=self.campuses[index],student_number=f"PRIVATE-{index}",admitted_on=timezone.localdate())
            course=Course.objects.create(code=f"C{index}",title="Course",department=self.departments[index],campus=self.campuses[index],term=self.term,instructor=self.president,published=True)
            Enrollment.objects.create(student=user,course=course)
            FinalGrade.objects.create(student=profile,course=course,letter="A",credits_earned=3,quality_points=4,released=index==0)
            Application.objects.create(applicant=user,program=program,campus=self.campuses[index],statement="Private application statement")
            self.profiles.append(profile);self.courses.append(course)
        self.assignment=DeanAssignment.objects.create(user=self.dean,department=self.departments[0])

    def report(self,owner=None,**values):
        return InstitutionalReport.objects.create(owner=owner or self.president,title="Synthetic report",dataset=values.pop("dataset","students"),group_by=values.pop("group_by","program"),**values)

    def test_dean_scope_and_president_dashboard_do_not_expose_individuals(self):
        report=self.report(self.dean)
        payload=execute_report(self.dean,report)
        self.assertEqual([row["label"] for row in payload["rows"]],["Program 0"])
        self.client.force_login(self.dean)
        response=self.client.get(reverse("leadership_dashboard",args=["dean"]))
        self.assertContains(response,"Program 0");self.assertNotContains(response,"Program 1")
        self.assertNotContains(response,"PRIVATE-")
        self.assertEqual(self.client.get(reverse("leadership_dashboard",args=["president"])).status_code,403)
        self.client.force_login(self.president)
        response=self.client.get(reverse("leadership_dashboard",args=["president"]))
        self.assertContains(response,"Program 1");self.assertNotContains(response,"Private application statement")

    def test_filters_dataset_validation_and_released_grade_metrics(self):
        report=self.report(dataset="enrollments",group_by="term",campus=self.campuses[1],term=self.term,status_filter="active")
        row=execute_report(self.president,report)["rows"][0]
        self.assertEqual(row["count"],1);self.assertEqual(row["unique_students"],1)
        report=self.report(dataset="grades",group_by="department")
        rows=execute_report(self.president,report)["rows"]
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]["earned_credits"],3)
        report.group_by="student__user__email"
        with self.assertRaises(ValidationError): execute_report(self.president,report)
        report=self.report(self.dean,department=self.departments[1])
        with self.assertRaises(PermissionDenied): execute_report(self.dean,report)

    def test_report_and_snapshot_access_rechecks_revoked_assignments(self):
        report=self.report(self.dean)
        snapshot=capture_report(self.dean,report,"Synthetic criterion","Institution evidence 1")
        self.assignment.active=False;self.assignment.save()
        with self.assertRaises(PermissionDenied): execute_report(self.dean,report)
        with self.assertRaises(PermissionDenied): snapshot_access(self.dean,snapshot)
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(reverse("report_snapshot",args=[snapshot.pk])).status_code,403)
        self.client.force_login(self.profiles[0].user)
        self.assertEqual(self.client.get(reverse("run_institutional_report",args=[report.pk])).status_code,403)

    def test_snapshot_is_fixed_requires_independent_review_and_detects_tampering(self):
        report=self.report()
        snapshot=capture_report(self.president,report,"Synthetic accreditation criterion","Reviewed evidence index")
        self.profiles[0].status="leave";self.profiles[0].save()
        self.assertEqual(snapshot.payload["rows"][0]["count"],1)
        with self.assertRaises(ValueError): snapshot.save()
        self.president.user_permissions.add(Permission.objects.get(codename="review_report_snapshot"))
        with self.assertRaises(PermissionDenied): review_snapshot(self.president,snapshot,True,"Self review")
        self.client.force_login(self.president)
        url=reverse("report_snapshot",args=[snapshot.pk])+"?format=csv"
        self.assertEqual(self.client.get(url).status_code,403)
        review_snapshot(self.reviewer,snapshot,True,"Scope and figures verified")
        review_snapshot(self.reviewer,snapshot,True,"Replay")
        self.assertEqual(ReportReview.objects.count(),1)
        self.assertEqual(self.client.get(url).status_code,200)
        with self.assertRaises(ValidationError): review_snapshot(self.reviewer,snapshot,False,"Change decision")
        payload=dict(snapshot.payload);payload["title"]="Altered"
        ReportSnapshot.objects.filter(pk=snapshot.pk).update(payload=payload)
        self.assertEqual(self.client.get(url).status_code,409)

    def test_csv_escapes_formula_labels_and_owner_isolation(self):
        program=self.profiles[0].program;program.name="=SUM(1,2)";program.save()
        report=self.report()
        self.client.force_login(self.president)
        response=self.client.get(reverse("run_institutional_report",args=[report.pk])+"?format=csv")
        self.assertContains(response,"'=SUM(1,2)");self.assertNotContains(response,"PRIVATE-")
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(reverse("run_institutional_report",args=[report.pk])).status_code,404)

    def test_campus_application_choice_and_unassigned_legacy_reporting(self):
        profile=self.profiles[0];profile.campus=None;profile.save()
        report=self.report(group_by="campus")
        self.assertIn("Unassigned",[row["label"] for row in execute_report(self.president,report)["rows"]])
        self.campuses[1].active=False;self.campuses[1].save()
        user=get_user_model().objects.create_user("applicant")
        self.client.force_login(user)
        response=self.client.post(reverse("admissions"),{"program":profile.program_id,"campus":self.campuses[1].pk,"statement":"Synthetic"})
        self.assertEqual(response.status_code,200);self.assertFalse(Application.objects.filter(applicant=user).exists())
        response=self.client.post(reverse("admissions"),{"program":profile.program_id,"campus":self.campuses[0].pk,"statement":"Synthetic"})
        self.assertEqual(response.status_code,302);self.assertEqual(Application.objects.get(applicant=user).campus_id,self.campuses[0].pk)
