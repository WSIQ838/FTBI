from datetime import timedelta
from io import StringIO
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.core.management import call_command
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.utils import timezone
from .models import Department,Program
from .registrar import StudentProfile
from .governance import InstitutionPolicy,PolicyRevision,PolicyReview,PolicyAcknowledgment,DemographicCollection,DemographicResponse,propose_revision,decide_policy,withdraw_policy,save_demographics,active_collection,demographic_counts


class GovernanceTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.author=users.create_user("author",is_staff=True)
        self.reviewer=users.create_user("reviewer",is_staff=True)
        self.reporter=users.create_user("reporter",is_staff=True)
        self.student=users.create_user("student")
        call_command("setup_roles",stdout=StringIO())
        for user,role in [(self.author,"Policy Authors"),(self.reviewer,"Policy Reviewers"),(self.reporter,"Demographic Reporting")]: user.groups.add(Group.objects.get(name=role))
        program=Program.objects.create(name="Program",department=Department.objects.create(name="Department"))
        self.profile=StudentProfile.objects.create(user=self.student,student_number="S1",program=program,admitted_on=timezone.localdate())
        self.policy=InstitutionPolicy.objects.create(code="optional-demographics",title="Synthetic voluntary demographic policy",kind="demographics")
        self.configuration={"questions":[{"key":"first_generation","label":"First-generation college student?","choices":[{"code":"yes","label":"Yes"},{"code":"no","label":"No"},{"code":"prefer_not","label":"Prefer not to answer"}]}]}

    def revision(self,**values):
        return propose_revision(self.policy,self.author,"Synthetic purpose, consent and retention statement",values.get("configuration",deepcopy(self.configuration)),values.get("effective_from",timezone.localdate()),values.get("expires"))

    def enabled(self):
        revision=self.revision()
        decide_policy(revision,self.reviewer,True,"Independent institutional review","Synthetic authority")
        control=DemographicCollection(pk=1,enabled=True,policy=self.policy);control.full_clean();control.save()
        return revision

    def test_independent_review_immutability_acknowledgment_and_replay(self):
        revision=self.revision()
        self.assertIsNone(self.policy.current_revision())
        self.author.user_permissions.add(Permission.objects.get(codename="approve_institution_policy"))
        with self.assertRaises(PermissionDenied): decide_policy(revision,self.author,True,"Self","Synthetic")
        for _ in range(2): decide_policy(revision,self.reviewer,True,"Reviewed","Synthetic authority")
        self.assertEqual(PolicyReview.objects.count(),1)
        with self.assertRaises(ValidationError): decide_policy(revision,self.reviewer,False,"Changed","Synthetic")
        with self.assertRaises(ValueError): revision.save()
        self.client.force_login(self.student)
        for _ in range(2): self.assertEqual(self.client.post(reverse("acknowledge_policy",args=[revision.pk])).status_code,302)
        self.assertEqual(PolicyAcknowledgment.objects.count(),1)
        self.assertFalse(DemographicResponse.objects.exists())

    def test_future_expired_and_withdrawn_versions_do_not_silently_reactivate_old_policy(self):
        first=self.enabled()
        future=self.revision(effective_from=timezone.localdate()+timedelta(days=1))
        decide_policy(future,self.reviewer,True,"Future approval","Synthetic")
        self.assertEqual(active_collection().pk,first.pk)
        withdrawn=self.revision()
        decide_policy(withdrawn,self.reviewer,True,"Current replacement","Synthetic")
        withdraw_policy(withdrawn,self.reviewer,"Institutional withdrawal")
        self.assertIsNone(active_collection())
        expired=self.revision(effective_from=timezone.localdate()-timedelta(days=2),expires=timezone.localdate()-timedelta(days=1))
        decide_policy(expired,self.reviewer,True,"Historical record","Synthetic")
        self.assertIsNone(active_collection())

    def test_choice_schema_rejects_unapproved_fields_and_missing_opt_out(self):
        for configuration in [{"questions":[]},{"questions":[{"key":[],"label":"Invalid","choices":[]}]},{"questions":[{"key":"medical_diagnosis","label":"Invalid","choices":[]}]}]:
            with self.assertRaises(ValidationError): self.revision(configuration=configuration)
        config=deepcopy(self.configuration);config["questions"][0]["choices"]=config["questions"][0]["choices"][:2]
        with self.assertRaises(ValidationError): self.revision(configuration=config)
        self.revision()
        self.policy.kind="academic"
        with self.assertRaises(ValidationError): self.policy.full_clean()

    def test_collection_requires_enablement_consent_and_current_policy(self):
        revision=self.revision()
        self.assertIsNone(active_collection())
        with self.assertRaises(ValidationError): save_demographics(self.profile,revision,{"first_generation":"yes"})
        decide_policy(revision,self.reviewer,True,"Reviewed","Synthetic")
        control=DemographicCollection(pk=1,enabled=True,policy=self.policy);control.full_clean();control.save()
        self.client.force_login(self.student)
        url=reverse("demographics")
        self.assertEqual(self.client.post(url,{"revision":revision.pk,"first_generation":"yes"}).status_code,200)
        self.assertFalse(DemographicResponse.objects.exists())
        self.assertEqual(self.client.post(url,{"revision":revision.pk,"first_generation":"yes","consent":"on"}).status_code,302)
        self.assertEqual(DemographicResponse.objects.get().answers,{"first_generation":"yes"})
        with self.assertRaises(ValidationError): save_demographics(self.profile,revision,{"first_generation":"unexpected"})
        next_revision=self.revision();decide_policy(next_revision,self.reviewer,True,"Revised criteria","Synthetic")
        with self.assertRaises(ValidationError): save_demographics(self.profile,revision,{"first_generation":"no"})
        self.assertEqual(self.client.post(url,{"revision":revision.pk,"first_generation":"no","consent":"on"}).status_code,200)
        self.assertEqual(DemographicResponse.objects.get().answers,{"first_generation":"yes"})

    def test_aggregate_small_cells_are_withheld_and_withdrawal_removes_current_answers(self):
        revision=self.enabled()
        save_demographics(self.profile,revision,{"first_generation":"yes"})
        self.assertTrue(demographic_counts(self.reporter)[0]["suppressed"])
        for index in range(4):
            user=get_user_model().objects.create_user(f"synthetic-{index}")
            student=StudentProfile.objects.create(user=user,student_number=f"T{index}",program=self.profile.program,admitted_on=timezone.localdate())
            save_demographics(student,revision,{"first_generation":"yes"})
        panel=demographic_counts(self.reporter)[0]
        self.assertFalse(panel["suppressed"]);self.assertEqual(panel["rows"][0]["count"],5)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("demographic_report")).status_code,403)
        self.assertEqual(self.client.get(reverse("withdraw_demographics")).status_code,405)
        self.assertEqual(self.client.post(reverse("withdraw_demographics")).status_code,302)
        self.assertFalse(DemographicResponse.objects.filter(student=self.profile).exists())
        panel=demographic_counts(self.reporter)[0]
        self.assertTrue(panel["suppressed"]);self.assertEqual(panel["rows"],[])

    def test_drafts_are_private_and_collection_stops_after_policy_withdrawal(self):
        draft=self.revision()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("policy_detail",args=[draft.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse("review_policy_revision",args=[draft.pk]),{}).status_code,403)
        decide_policy(draft,self.reviewer,True,"Reviewed","Synthetic")
        DemographicCollection.objects.create(pk=1,enabled=True,policy=self.policy)
        save_demographics(self.profile,draft,{"first_generation":"yes"})
        withdraw_policy(draft,self.reviewer,"Policy withdrawn")
        self.assertEqual(self.client.post(reverse("demographics"),{"revision":draft.pk,"consent":"on"}).status_code,403)
        self.assertEqual(demographic_counts(self.reporter),[])
        self.assertEqual(self.client.post(reverse("withdraw_demographics")).status_code,302)
        self.assertFalse(DemographicResponse.objects.exists())
