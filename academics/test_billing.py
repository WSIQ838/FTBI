import uuid
import json
import time
import hmac
import hashlib
from unittest.mock import patch
from types import SimpleNamespace
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import Department,Program,Term,Course,Enrollment
from .registrar import StudentProfile
from .services import LedgerEntry
from .payments import PaymentRequest
from .billing import TuitionSchedule, Invoice, issue_invoice, bill_schedule, verify_manual_payment, allocate_payment, create_plan, installment_balances


class BillingTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        self.finance=users.create_user("finance",is_staff=True)
        self.finance.user_permissions.set(Permission.objects.filter(content_type__app_label="academics",codename__in=["view_invoice","add_invoice","change_paymentrequest","view_paymentrequest","view_ledgerentry","add_paymentplan","add_paymentallocation"]))
        d=Department.objects.create(name="Finance")
        self.program=Program.objects.create(name="Program",department=d)
        self.profile=StudentProfile.objects.create(user=self.student,student_number="STUDENT",program=self.program,admitted_on=timezone.localdate())
        self.term=Term.objects.create(name="Fall",starts=timezone.localdate(),ends=timezone.localdate()+timedelta(days=90))
        c=Course.objects.create(code="A",title="A",department=d,term=self.term,instructor=self.finance,credits=3)
        Enrollment.objects.create(student=self.student,course=c)

    def invoice(self,amount=100):
        return issue_invoice(self.profile,"Tuition",amount,timezone.localdate(),str(uuid.uuid4()),self.finance)[0]

    def payment(self,amount=100):
        item=PaymentRequest.objects.create(student=self.profile,amount=amount,reference="Bank confirmed")
        return verify_manual_payment(item,self.finance)

    def test_billing_rerun_and_manual_verification_are_idempotent(self):
        schedule=TuitionSchedule.objects.create(program=self.program,term=self.term,per_credit=100,term_fee=20,due=timezone.localdate(),active=True)
        self.assertEqual(bill_schedule(schedule),2)
        self.assertEqual(bill_schedule(schedule),0)
        self.assertEqual(sum(Invoice.objects.values_list("amount",flat=True)),320)
        payment=self.payment(50)
        verify_manual_payment(payment,self.finance)
        self.assertEqual(LedgerEntry.objects.filter(amount=-50).count(),1)
        self.assertIsNotNone(payment.ledger_id)

    def test_allocations_cannot_overpay_and_replay_is_safe(self):
        invoice=self.invoice(); payment=self.payment(150); token=uuid.uuid4()
        allocate_payment(payment,invoice,Decimal(60),self.finance,token)
        allocate_payment(payment,invoice,Decimal(60),self.finance,token)
        self.assertEqual(invoice.balance,40)
        with self.assertRaises(ValidationError): allocate_payment(payment,invoice,50,self.finance,uuid.uuid4())
        with self.assertRaises(ValidationError): allocate_payment(payment,invoice,40,self.finance,token)
        self.assertEqual(invoice.balance,40)
        other=StudentProfile.objects.create(user=self.other,student_number="OTHER",program=self.program,admitted_on=timezone.localdate())
        foreign=PaymentRequest.objects.create(student=other,amount=100,status="verified")
        with self.assertRaises(ValidationError): allocate_payment(foreign,invoice,20,self.finance,uuid.uuid4())

    def test_plan_totals_and_installment_application(self):
        invoice=self.invoice()
        today=timezone.localdate()
        with self.assertRaises(ValidationError): create_plan(invoice,[(today,Decimal(99))],self.finance)
        create_plan(invoice,[(today,Decimal(40)),(today+timedelta(days=30),Decimal(60))],self.finance)
        payment=self.payment(50)
        allocate_payment(payment,invoice,50,self.finance,uuid.uuid4())
        self.assertEqual([balance for _,balance in installment_balances(invoice)],[0,50])
        with self.assertRaises(ValidationError): create_plan(invoice,[(today,Decimal(100))],self.finance)

    def test_permissions_and_private_receipts(self):
        invoice=self.invoice(); payment=self.payment()
        url=reverse("invoice",args=[invoice.pk]); receipt=reverse("payment_receipt",args=[payment.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get(receipt).status_code,404)
        self.assertEqual(self.client.get(reverse("finance")).status_code,403)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(url),"Tuition")
        self.assertTrue(self.client.get(receipt).content.startswith(b"%PDF"))
        self.assertEqual(self.client.post(reverse("verify_payment",args=[payment.pk])).status_code,403)
        self.client.force_login(self.finance)
        self.assertEqual(self.client.get(reverse("financial_reconciliation")).status_code,200)
        self.assertEqual(self.client.get(reverse("verify_payment",args=[payment.pk])).status_code,405)

    @override_settings(FTBI_STRIPE_ENABLED=True,STRIPE_WEBHOOK_SECRET="test-secret")
    def test_real_signature_validation_amount_check_and_webhook_replay(self):
        payment=PaymentRequest.objects.create(student=self.profile,amount=25,reference="stripe:cs_test")
        def send(amount,secret="test-secret"):
            payload=json.dumps({"id":"evt_test","type":"checkout.session.completed","data":{"object":{"id":"cs_test","payment_status":"paid","metadata":{"ftbi_payment_id":str(payment.pk)},"currency":"usd","amount_total":amount}}}).encode()
            stamp=str(int(time.time()))
            signature=hmac.new(secret.encode(),stamp.encode()+b"."+payload,hashlib.sha256).hexdigest()
            return self.client.post(reverse("stripe_webhook"),payload,content_type="application/json",HTTP_STRIPE_SIGNATURE=f"t={stamp},v1={signature}")
        self.assertEqual(send(2500,"wrong-secret").status_code,400)
        self.assertEqual(send(2600).status_code,400)
        self.assertEqual(send(2500).status_code,200)
        self.assertEqual(send(2500).status_code,200)
        payment.refresh_from_db()
        self.assertEqual(payment.status,"verified")
        self.assertEqual(payment.ledger.amount,-25)
        self.assertEqual(LedgerEntry.objects.filter(student=self.profile).count(),1)

    def test_processor_payment_cannot_be_manually_verified(self):
        payment=PaymentRequest.objects.create(student=self.profile,amount=25,reference="stripe:cs_test")
        with self.assertRaises(ValidationError): verify_manual_payment(payment,self.finance)
        self.assertEqual(LedgerEntry.objects.count(),0)

    @override_settings(FTBI_STRIPE_ENABLED=True,STRIPE_SECRET_KEY="test",FTBI_PUBLIC_ORIGIN="https://college.example")
    @patch("academics.checkout.stripe.checkout.Session.retrieve")
    @patch("academics.checkout.stripe.checkout.Session.create")
    def test_partial_checkout_reuses_pending_session(self,create,retrieve):
        self.invoice(100)
        create.return_value=SimpleNamespace(id="cs_partial",url="https://checkout.stripe.com/test")
        retrieve.return_value=SimpleNamespace(status="open",url="https://checkout.stripe.com/test")
        self.client.force_login(self.student)
        url=reverse("checkout")
        self.assertEqual(self.client.post(url,{"amount":"101"}).status_code,400)
        self.assertEqual(self.client.post(url,{"amount":"NaN"}).status_code,400)
        self.assertEqual(self.client.post(url,{"amount":"40"}).status_code,302)
        self.assertEqual(self.client.post(url,{"amount":"40"}).status_code,302)
        self.assertEqual(self.client.post(url,{"amount":"20"}).status_code,409)
        self.assertEqual(PaymentRequest.objects.count(),1)
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"],4000)
