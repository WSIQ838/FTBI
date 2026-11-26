import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission
from . import test_billing
from .billing import issue_invoice,allocate_payment,verify_manual_payment,create_plan
from .payments import PaymentRequest
from .services import LedgerEntry
from .models import Course,Enrollment
from .registrar import RegistrationWindow
from .finance_adjustments import PaymentAdjustment,AllocationReduction,PaymentDispute,FinancialHoldPolicy,record_adjustment,open_dispute,resolve_dispute,evaluate_financial_hold,net_payment,allocated_payment
from .notification_models import DurableNotification


class FinanceAdjustmentTests(TestCase):
    def setUp(self):
        test_billing.BillingTests.setUp(self)
        self.finance.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))

    def invoice(self,amount=100,due=None):
        return issue_invoice(self.profile,"Tuition",amount,due or timezone.localdate()-timedelta(days=10),str(uuid.uuid4()),self.finance)[0]

    def payment(self,amount=100):
        return verify_manual_payment(PaymentRequest.objects.create(student=self.profile,amount=amount,reference="Confirmed bank payment"),self.finance)

    def adjustment(self,payment,amount,**extra):
        return record_adjustment(payment,"refund",amount,extra.get("reference",str(uuid.uuid4())),"Confirmed external refund",self.finance,extra.get("token",uuid.uuid4()))

    def test_partial_refund_releases_allocations_without_rewriting_evidence(self):
        invoice=self.invoice();payment=self.payment(150)
        allocation=allocate_payment(payment,invoice,100,self.finance,uuid.uuid4())
        refund=self.adjustment(payment,75)
        allocation.refresh_from_db()
        self.assertEqual(allocation.amount,100)
        self.assertEqual(AllocationReduction.objects.get().amount,25)
        self.assertEqual(invoice.balance,25)
        self.assertEqual(net_payment(payment),75)
        self.assertEqual(sum(LedgerEntry.objects.values_list("amount",flat=True)),25)
        with self.assertRaises(ValidationError): allocate_payment(payment,invoice,1,self.finance,uuid.uuid4())
        with self.assertRaises(ValueError): refund.save()

    def test_refund_replay_limits_and_processor_boundaries(self):
        payment=self.payment();token=uuid.uuid4()
        first=self.adjustment(payment,40,token=token,reference="bank-refund-1")
        self.assertEqual(first.pk,self.adjustment(payment,40,token=token,reference="bank-refund-1").pk)
        for amount in [61,0,-1,Decimal("0.001")]:
            with self.assertRaises(ValidationError): self.adjustment(payment,amount)
        with self.assertRaises(ValidationError): self.adjustment(payment,41,token=token,reference="bank-refund-1")
        with self.assertRaises(ValidationError): self.adjustment(payment,40,reference="bank-refund-1")
        payment.reference="stripe:cs_synthetic";payment.save(update_fields=["reference"])
        with self.assertRaises(ValidationError): self.adjustment(payment,10)
        self.assertEqual(PaymentAdjustment.objects.count(),1)

    def test_dispute_withholding_and_recovery_are_once_only(self):
        invoice=self.invoice();payment=self.payment()
        allocate_payment(payment,invoice,100,self.finance,uuid.uuid4())
        token=uuid.uuid4()
        dispute=open_dispute(payment,40,"bank-case-1","Confirmed funds withheld",self.finance,token)
        self.assertEqual(open_dispute(payment,40,"bank-case-1","Confirmed funds withheld",self.finance,token).pk,dispute.pk)
        self.assertEqual(invoice.balance,40)
        with self.assertRaises(ValidationError): self.adjustment(payment,10)
        with self.assertRaises(ValidationError): allocate_payment(payment,invoice,10,self.finance,uuid.uuid4())
        for _ in range(2): resolve_dispute(dispute,"won","Funds restored","bank-restoration-1",self.finance,uuid.uuid4())
        self.assertEqual(PaymentAdjustment.objects.count(),2)
        self.assertEqual(net_payment(payment),100)
        self.assertEqual(allocated_payment(payment),60)
        allocate_payment(payment,invoice,40,self.finance,uuid.uuid4())
        self.assertEqual(invoice.balance,0)
        with self.assertRaises(ValidationError): resolve_dispute(dispute,"lost","Changed outcome","",self.finance,uuid.uuid4())

    def test_lost_dispute_does_not_post_second_debit(self):
        payment=self.payment()
        dispute=open_dispute(payment,100,"case-lost","Withheld",self.finance,uuid.uuid4())
        resolve_dispute(dispute,"lost","Final loss evidence","",self.finance,uuid.uuid4())
        self.assertEqual(PaymentAdjustment.objects.count(),1)
        self.assertEqual(net_payment(payment),0)
        self.assertEqual(PaymentDispute.objects.get().status,"lost")

    def test_hold_policy_is_disabled_by_default_and_preserves_manual_holds(self):
        self.invoice()
        self.profile.registration_hold=True;self.profile.save(update_fields=["registration_hold"])
        self.assertFalse(evaluate_financial_hold(self.profile).active)
        policy=FinancialHoldPolicy(enabled=True,overdue_threshold=50)
        with self.assertRaises(ValidationError): policy.save()
        policy.approval_reference="Synthetic approved policy";policy.save()
        self.assertTrue(evaluate_financial_hold(self.profile).active)
        evaluate_financial_hold(self.profile)
        self.assertEqual(DurableNotification.objects.filter(subject="Financial registration hold updated").count(),1)
        self.payment(60)
        self.assertFalse(evaluate_financial_hold(self.profile).active)
        self.profile.refresh_from_db();self.assertTrue(self.profile.registration_hold)
        self.assertEqual(DurableNotification.objects.filter(subject="Financial registration hold updated").count(),2)

    def test_hold_respects_installments_grace_and_current_registration(self):
        invoice=self.invoice()
        today=timezone.localdate()
        create_plan(invoice,[(today-timedelta(days=2),Decimal(40)),(today+timedelta(days=30),Decimal(60))],self.finance)
        policy=FinancialHoldPolicy(enabled=True,overdue_threshold=30,grace_days=3,approval_reference="Synthetic");policy.save()
        self.assertFalse(evaluate_financial_hold(self.profile).active)
        policy.grace_days=0;policy.save()
        self.assertEqual(evaluate_financial_hold(self.profile).overdue_amount,40)
        course=Course.objects.get();course.published=True;course.save()
        Enrollment.objects.all().delete()
        window=RegistrationWindow.objects.create(course=course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),capacity=5)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("register",args=[window.pk])).status_code,403)
        self.payment(100)
        self.assertEqual(self.client.post(reverse("register",args=[window.pk])).status_code,302)
        self.assertEqual(Enrollment.objects.filter(active=True).count(),1)

    def test_unallocated_credit_reduces_overdue_before_future_obligations(self):
        self.invoice(100)
        self.invoice(200,timezone.localdate()+timedelta(days=30))
        FinancialHoldPolicy(enabled=True,overdue_threshold=60,approval_reference="Synthetic").save()
        self.payment(50)
        hold=evaluate_financial_hold(self.profile)
        self.assertEqual(hold.overdue_amount,50)
        self.assertFalse(hold.active)

    def test_adjustment_permissions_private_history_and_net_report(self):
        self.invoice();payment=self.payment()
        self.client.force_login(self.student)
        url=reverse("payment_adjustment",args=[payment.pk,"refund"])
        self.assertEqual(self.client.post(url,{}).status_code,403)
        self.client.force_login(self.finance)
        self.assertContains(self.client.get(url),"does not send money")
        data={"amount":"25","reference":"private-bank-ref","reason":"Private reviewed evidence","confirmed":"on","token":str(uuid.uuid4())}
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(self.client.post(url,data).status_code,302)
        report=self.client.get(reverse("financial_reconciliation"))
        self.assertContains(report,"net_payment")
        self.assertContains(report,"25.00")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("payment_history")),"Original amount")
        self.client.force_login(self.student)
        response=self.client.get(reverse("payment_history"))
        self.assertContains(response,"75.00");self.assertNotContains(response,"Private reviewed evidence")
        self.assertNotContains(response,"private-bank-ref")
