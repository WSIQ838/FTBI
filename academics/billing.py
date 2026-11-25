"""Audited billing services. Monetary writes serialize on the student account."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone
from .models import Program, Term, Enrollment
from .registrar import StudentProfile
from .services import LedgerEntry
from .payments import PaymentRequest
from .operations import AuditEvent
from .notification_models import notify


class TuitionSchedule(models.Model):
    program=models.ForeignKey(Program,on_delete=models.PROTECT)
    term=models.ForeignKey(Term,on_delete=models.PROTECT)
    per_credit=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(0)])
    term_fee=models.DecimalField(max_digits=10,decimal_places=2,default=0,validators=[MinValueValidator(0)])
    due=models.DateField()
    active=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["program","term"],name="unique_tuition_schedule")]


class Invoice(models.Model):
    identifier=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    description=models.CharField(max_length=200)
    amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    due=models.DateField()
    created=models.DateTimeField(auto_now_add=True)
    source_key=models.CharField(max_length=150,unique=True)
    ledger=models.OneToOneField(LedgerEntry,on_delete=models.PROTECT)

    @property
    def paid(self):
        from .finance_adjustments import AllocationReduction,total
        return total(self.allocations.all())-total(AllocationReduction.objects.filter(allocation__invoice=self))

    @property
    def balance(self):
        return self.amount-self.paid


class PaymentAllocation(models.Model):
    payment=models.ForeignKey(PaymentRequest,on_delete=models.PROTECT,related_name="allocations")
    invoice=models.ForeignKey(Invoice,on_delete=models.PROTECT,related_name="allocations")
    amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["payment","invoice"],name="unique_payment_invoice")]


class PaymentPlan(models.Model):
    invoice=models.OneToOneField(Invoice,on_delete=models.PROTECT,related_name="plan")
    approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)


class AllocationOperation(models.Model):
    token=models.UUIDField(unique=True)
    allocation=models.ForeignKey(PaymentAllocation,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=12,decimal_places=2)


class Installment(models.Model):
    plan=models.ForeignKey(PaymentPlan,on_delete=models.PROTECT,related_name="installments")
    due=models.DateField()
    amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    class Meta:
        ordering=["due","pk"]


@transaction.atomic
def issue_invoice(student,description,amount,due,source_key,actor=None):
    StudentProfile.objects.select_for_update().get(pk=student.pk)
    existing=Invoice.objects.filter(source_key=source_key).first()
    if existing:
        if existing.student_id != student.pk:
            raise ValidationError("Invoice source is already in use.")
        return existing,False
    amount=Decimal(amount)
    if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal("0.01")):
        raise ValidationError("Invoice amount must be positive with at most two decimals.")
    ledger=LedgerEntry.objects.create(student=student,description=description,amount=amount,posted=timezone.localdate(),released=True)
    invoice=Invoice(student=student,description=description,amount=amount,due=due,source_key=source_key,ledger=ledger)
    invoice.full_clean(); invoice.save()
    AuditEvent.objects.create(actor=actor,action="invoice_issued",target=str(invoice.identifier))
    return invoice,True


@transaction.atomic
def verify_manual_payment(payment,actor):
    StudentProfile.objects.select_for_update().get(pk=payment.student_id)
    payment=PaymentRequest.objects.select_for_update().get(pk=payment.pk)
    if payment.reference.startswith("stripe:"):
        raise ValidationError("Processor payments must be verified by signed webhooks.")
    if payment.status=="verified":
        return payment
    if payment.status!="pending":
        raise ValidationError("Only pending payments can be verified.")
    payment.full_clean()
    payment.ledger=LedgerEntry.objects.create(student_id=payment.student_id,description=f"Verified payment #{payment.pk}",amount=-payment.amount,posted=timezone.localdate(),released=True)
    payment.status="verified"; payment.reviewed_by=actor
    payment.save(update_fields=["status","reviewed_by","ledger"])
    AuditEvent.objects.create(actor=actor,action="manual_payment_verified",target=str(payment.pk))
    notify(payment.student.user,"payment","Payment confirmed","A verified payment has been credited to your account. View the private receipt in Payments.",f"payment-confirmed:{payment.pk}")
    return payment


@transaction.atomic
def allocate_payment(payment,invoice,amount,actor,token):
    StudentProfile.objects.select_for_update().get(pk=invoice.student_id)
    payment=PaymentRequest.objects.select_for_update().get(pk=payment.pk)
    invoice=Invoice.objects.select_for_update().get(pk=invoice.pk)
    amount=Decimal(amount)
    prior=AllocationOperation.objects.filter(token=token).select_related("allocation").first()
    if prior:
        if prior.allocation.invoice_id!=invoice.pk or prior.allocation.payment_id!=payment.pk or prior.amount!=amount:
            raise ValidationError("This allocation request was already used with different details.")
        return prior.allocation
    if payment.student_id!=invoice.student_id or payment.status!="verified":
        raise ValidationError("Use a verified payment from this student.")
    from .finance_adjustments import net_payment,allocated_payment
    if payment.disputes.filter(status="open").exists(): raise ValidationError("Resolve the open payment dispute before allocation.")
    used=allocated_payment(payment)
    if not amount.is_finite() or amount<=0 or amount>invoice.balance or amount>net_payment(payment)-used or amount!=amount.quantize(Decimal("0.01")):
        raise ValidationError("Allocation exceeds the invoice balance or available payment.")
    entry=PaymentAllocation.objects.filter(payment=payment,invoice=invoice).first()
    if entry:
        entry.amount+=amount; entry.save(update_fields=["amount"])
    else:
        entry=PaymentAllocation.objects.create(payment=payment,invoice=invoice,amount=amount)
    AllocationOperation.objects.create(token=token,allocation=entry,amount=amount)
    AuditEvent.objects.create(actor=actor,action="payment_allocated",target=str(entry.pk))
    return entry


@transaction.atomic
def create_plan(invoice,installments,actor):
    StudentProfile.objects.select_for_update().get(pk=invoice.student_id)
    invoice=Invoice.objects.select_for_update().get(pk=invoice.pk)
    if PaymentPlan.objects.filter(invoice=invoice).exists() or invoice.paid:
        raise ValidationError("Create a plan once, before allocating any payments.")
    if not installments or sum(amount for _,amount in installments)!=invoice.amount:
        raise ValidationError("Installments must total the full invoice amount.")
    plan=PaymentPlan.objects.create(invoice=invoice,approved_by=actor)
    for due,amount in installments:
        item=Installment(plan=plan,due=due,amount=amount); item.full_clean(); item.save()
    AuditEvent.objects.create(actor=actor,action="payment_plan_approved",target=str(plan.pk))
    return plan


def installment_balances(invoice):
    paid=invoice.paid
    result=[]
    for item in invoice.plan.installments.all():
        applied=min(paid,item.amount); paid-=applied
        result.append((item,item.amount-applied))
    return result


def bill_schedule(schedule,actor=None):
    """One tuition invoice per enrollment and one term fee per student; safe to rerun."""
    count=0
    if not schedule.active:
        raise ValidationError("Activate the approved tuition schedule first.")
    for profile in StudentProfile.objects.filter(program=schedule.program,status="active"):
        enrollments=list(Enrollment.objects.filter(student=profile.user,active=True,course__term=schedule.term).select_related("course"))
        for enrollment in enrollments:
            amount=schedule.per_credit*enrollment.course.credits
            if amount:
                _,created=issue_invoice(profile,f"Tuition: {enrollment.course.code} {schedule.term.name}",amount,schedule.due,f"tuition:{enrollment.pk}",actor)
                count+=created
        if enrollments and schedule.term_fee:
            _,created=issue_invoice(profile,f"Term fees: {schedule.term.name}",schedule.term_fee,schedule.due,f"term-fee:{schedule.term_id}:{profile.pk}",actor)
            count+=created
    return count
