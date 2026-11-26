from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from . import test_billing
from .models import Term,Course
from .registrar import StudentProfile
from .services import FinalGrade,LedgerEntry
from .operations import FinancialAidAward
from .scholarships import ScholarshipFund,ScholarshipApplication,ScholarshipAward,ScholarshipEvent,submit_application,decide_application,change_award


class ScholarshipTests(TestCase):
    def setUp(self):
        test_billing.BillingTests.setUp(self)
        self.finance.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        self.fund=ScholarshipFund.objects.create(code="MERIT",name="Demonstration merit fund",term=self.term,description="Institution-reviewed academic award",budget=1000,maximum_award=800,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),published=True,approval_reference="Synthetic approval")

    def application(self,amount=500):
        return submit_application(self.profile,self.fund,amount,"My synthetic statement")

    def award(self,amount=500):
        item=self.application(amount)
        decide_application(item,"approved","Approved under published criteria",self.finance,amount)
        return ScholarshipAward.objects.get(application=item)

    def test_approval_reserves_budget_and_posting_and_reversal_are_once_only(self):
        award=self.award()
        self.assertEqual(self.fund.committed,500)
        self.assertFalse(LedgerEntry.objects.exists())
        self.assertEqual(FinancialAidAward.objects.get().status,"approved")
        for _ in range(2): change_award(award,"post","Authorized tuition credit",self.finance)
        self.assertEqual(LedgerEntry.objects.count(),1)
        self.assertEqual(LedgerEntry.objects.get().amount,-500)
        for _ in range(2): change_award(award,"reverse","Approved correction; student informed",self.finance)
        self.assertEqual(LedgerEntry.objects.count(),2)
        self.assertEqual(sum(LedgerEntry.objects.values_list("amount",flat=True)),0)
        self.assertEqual(self.fund.committed,0)
        self.assertEqual(ScholarshipEvent.objects.count(),4)
        with self.assertRaises(ValidationError): change_award(award,"post","Repeat after reversal",self.finance)

    def test_fund_budget_cannot_be_overcommitted_or_reduced_below_awards(self):
        self.award(800)
        other=StudentProfile.objects.create(user=self.other,program=self.program,student_number="S02",admitted_on=timezone.localdate())
        item=submit_application(other,self.fund,300,"Second applicant")
        with self.assertRaises(ValidationError): decide_application(item,"approved","Review",self.finance,300)
        self.assertEqual(ScholarshipAward.objects.count(),1)
        self.fund.budget=700
        with self.assertRaises(ValidationError): self.fund.save()
        self.fund.refresh_from_db();self.assertEqual(self.fund.budget,1000)

    def test_eligibility_rechecked_on_approval_and_policy_is_snapshotted(self):
        course=Course.objects.get();self.term.ends=timezone.localdate();self.term.save()
        grade=FinalGrade.objects.create(student=self.profile,course=course,letter="A",quality_points=4,credits_earned=3,released=True)
        self.fund.minimum_gpa=3;self.fund.minimum_credits=3;self.fund.save()
        item=self.application()
        grade.quality_points=2;grade.save()
        with self.assertRaises(ValidationError): decide_application(item,"approved","Review",self.finance,500)
        grade.quality_points=4;grade.save()
        decide_application(item,"approved","Review",self.finance,500)
        award=ScholarshipAward.objects.get()
        self.fund.name="New label";self.fund.minimum_gpa=2;self.fund.save()
        self.assertEqual(award.approval_snapshot["minimum_gpa"],"3.00")
        self.assertEqual(award.approval_snapshot["fund_name"],"Demonstration merit fund")
        with self.assertRaises(ValidationError): decide_application(item,"approved","Changed request",self.finance,600)

    def test_closed_duplicate_ineligible_and_self_approval_blocked(self):
        self.fund.closes=timezone.now()-timedelta(seconds=1);self.fund.save()
        with self.assertRaises(ValidationError): self.application()
        self.fund.closes=timezone.now()+timedelta(days=1);self.fund.minimum_gpa=3;self.fund.save()
        with self.assertRaises(ValidationError): self.application()
        self.fund.minimum_gpa=None;self.fund.save()
        item=self.application()
        with self.assertRaises(ValidationError): self.application()
        with self.assertRaises(ValidationError): decide_application(item,"approved","Self review",self.student,500)
        decide_application(item,"withdrawn","Changed plans",self.student)
        with self.assertRaises(ValidationError): decide_application(item,"approved","Too late",self.finance,500)

    def test_owner_scoping_review_permissions_and_cancelled_budget(self):
        item=self.application()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("scholarship_application",args=[item.pk])).status_code,404)
        self.client.force_login(self.student)
        decision=reverse("decide_scholarship",args=[item.pk])
        self.assertEqual(self.client.post(decision,{"outcome":"approved","amount":"500","reason":"Self review"}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.status,"pending")
        self.client.force_login(self.finance)
        self.assertEqual(self.client.post(decision,{"outcome":"approved","amount":"500","reason":"Approved review"}).status_code,302)
        award=ScholarshipAward.objects.get()
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("scholarship_award_action",args=[award.pk,"post"]),{"confirmed":"on","reason":"Attempt"}).status_code,403)
        self.assertContains(self.client.get(reverse("scholarship_application",args=[item.pk])),"Approved review")
        change_award(award,"cancel","Funding correction before posting",self.finance)
        self.assertEqual(self.fund.committed,0)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_renewal_links_only_own_posted_award_from_prior_fund_term(self):
        award=self.award();change_award(award,"post","Approved",self.finance)
        future=Term.objects.create(name="Following year",starts=self.term.ends+timedelta(days=1),ends=self.term.ends+timedelta(days=100))
        next_fund=ScholarshipFund.objects.create(code="MERIT",name="Renewal",term=future,description="Renewal review",budget=1000,maximum_award=500,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),published=True,approval_reference="Renewal policy")
        other=StudentProfile.objects.create(user=self.other,program=self.program,student_number="S02",admitted_on=timezone.localdate())
        with self.assertRaises(ValidationError): submit_application(other,next_fund,500,"Invalid renewal",award)
        item=submit_application(self.profile,next_fund,500,"Renewal statement",award)
        self.assertEqual(item.renewal_of_id,award.pk)
        self.assertEqual(item.status,"pending")
        self.assertEqual(next_fund.committed,0)
