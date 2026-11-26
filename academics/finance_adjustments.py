"""Append-only payment adjustments and independent registration hold policy."""
import uuid
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .registrar import StudentProfile
from .payments import PaymentRequest
from .services import LedgerEntry
from .billing import Invoice, PaymentAllocation, PaymentPlan, installment_balances
from .operations import AuditEvent
from .notification_models import notify


def total(rows): return rows.aggregate(total=Sum("amount"))["total"] or Decimal(0)


class PaymentAdjustment(models.Model):
    payment=models.ForeignKey(PaymentRequest,on_delete=models.PROTECT,related_name="adjustments")
    kind=models.CharField(max_length=12,choices=[("refund","Refund"),("chargeback","Funds withheld"),("recovery","Funds restored")])
    amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))])
    token=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    reference=models.CharField(max_length=160,unique=True)
    reason=models.TextField(max_length=2000)
    original=models.ForeignKey("self",on_delete=models.PROTECT,null=True,blank=True,related_name="recoveries")
    ledger=models.OneToOneField(LedgerEntry,on_delete=models.PROTECT,related_name="payment_adjustment")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name="positive_payment_adjustment")]
    def save(self,*args,**kwargs):
        if self.pk: raise ValueError("Payment adjustments are immutable.")
        super().save(*args,**kwargs)


class AllocationReduction(models.Model):
    adjustment=models.ForeignKey(PaymentAdjustment,on_delete=models.PROTECT)
    allocation=models.ForeignKey(PaymentAllocation,on_delete=models.PROTECT,related_name="reductions")
    amount=models.DecimalField(max_digits=12,decimal_places=2)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["adjustment","allocation"],name="one_adjustment_allocation_reduction"),models.CheckConstraint(condition=models.Q(amount__gt=0),name="positive_allocation_reduction")]


class PaymentDispute(models.Model):
    payment=models.ForeignKey(PaymentRequest,on_delete=models.PROTECT,related_name="disputes")
    debit=models.OneToOneField(PaymentAdjustment,on_delete=models.PROTECT,related_name="dispute")
    status=models.CharField(max_length=10,choices=[("open","Open"),("won","Won"),("lost","Lost")],default="open")
    reason=models.TextField(max_length=2000)
    resolution=models.TextField(max_length=2000,blank=True)
    resolved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
    resolved_at=models.DateTimeField(null=True,blank=True)
    recovery=models.OneToOneField(PaymentAdjustment,on_delete=models.PROTECT,null=True,blank=True,related_name="recovered_dispute")


class FinancialHoldPolicy(models.Model):
    enabled=models.BooleanField(default=False)
    overdue_threshold=models.DecimalField(max_digits=12,decimal_places=2,default=100,validators=[MinValueValidator(Decimal("0.01"))])
    grace_days=models.PositiveSmallIntegerField(default=0,validators=[MaxValueValidator(365)])
    approval_reference=models.CharField(max_length=200,blank=True)
    def clean(self):
        if self.enabled and not self.approval_reference.strip(): raise ValidationError("An enabled financial hold policy needs institutional approval.")
    def save(self,*args,**kwargs):
        self.pk=1; self.full_clean();super().save(*args,**kwargs)


class FinancialHold(models.Model):
    student=models.OneToOneField(StudentProfile,on_delete=models.PROTECT,related_name="financial_hold")
    active=models.BooleanField(default=False)
    overdue_amount=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    policy_snapshot=models.JSONField(default=dict)
    evaluated=models.DateTimeField(auto_now=True)


def net_payment(payment):
    return payment.amount-total(payment.adjustments.exclude(kind="recovery"))+total(payment.adjustments.filter(kind="recovery"))


def allocated_payment(payment):
    return total(payment.allocations.all())-total(AllocationReduction.objects.filter(allocation__payment=payment))


@transaction.atomic
def record_adjustment(payment,kind,amount,reference,reason,actor,token,original=None):
    StudentProfile.objects.select_for_update().get(pk=payment.student_id)
    payment=PaymentRequest.objects.select_for_update().get(pk=payment.pk)
    amount=Decimal(amount);reference=reference.strip();reason=reason.strip()
    prior=PaymentAdjustment.objects.filter(token=token).first()
    if prior:
        if (prior.payment_id,prior.kind,prior.amount,prior.reference,prior.original_id)!=(payment.pk,kind,amount,reference,original.pk if original else None):
            raise ValidationError("Adjustment request already used with different details.")
        return prior
    if payment.reference.startswith("stripe:"):
        raise ValidationError("Processor refunds and disputes require provider reconciliation; manual posting is disabled.")
    if payment.status!="verified" or not payment.ledger_id:
        raise ValidationError("Use a verified payment with a linked ledger entry.")
    if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal("0.01")) or kind not in {"refund","chargeback","recovery"}:
        raise ValidationError("Enter a positive amount with at most two decimals.")
    if not reference or not reason: raise ValidationError("External evidence reference and reason are required.")
    if PaymentAdjustment.objects.filter(reference=reference).exists(): raise ValidationError("Evidence reference was already recorded.")
    if kind=="recovery":
        if not original or original.payment_id!=payment.pk or original.kind!="chargeback" or amount>original.amount-total(original.recoveries.all()):
            raise ValidationError("Recovery exceeds its original withheld funds.")
    else:
        if original or amount>net_payment(payment): raise ValidationError("Adjustment exceeds the remaining payment.")
        if payment.disputes.filter(status="open").exists(): raise ValidationError("Resolve the open dispute before another refund or dispute.")
    ledger=LedgerEntry.objects.create(student=payment.student,description=f"Payment {kind} #{payment.pk}",amount=-amount if kind=="recovery" else amount,posted=timezone.localdate(),released=True)
    adjustment=PaymentAdjustment(payment=payment,kind=kind,amount=amount,token=token,reference=reference,reason=reason,actor=actor,original=original,ledger=ledger)
    adjustment.full_clean();adjustment.save()
    if kind!="recovery":
        # Preserve original allocations. Consume unallocated credit first, then release newest allocations.
        release=max(allocated_payment(payment)-net_payment(payment),Decimal(0))
        for allocation in payment.allocations.order_by("-pk"):
            if not release: break
            available=allocation.amount-total(allocation.reductions.all())
            reduction=min(release,available)
            if reduction: AllocationReduction.objects.create(adjustment=adjustment,allocation=allocation,amount=reduction)
            release-=reduction
    AuditEvent.objects.create(actor=actor,action="payment_"+kind,target=str(adjustment.pk))
    notify(payment.student.user,"payment","Payment adjustment recorded","Finance recorded a payment adjustment. Review your payment history and contact finance with questions.",f"payment-adjustment:{adjustment.pk}")
    return adjustment


@transaction.atomic
def open_dispute(payment,amount,reference,reason,actor,token):
    debit=record_adjustment(payment,"chargeback",amount,reference,reason,actor,token)
    dispute,_=PaymentDispute.objects.get_or_create(debit=debit,defaults={"payment":payment,"reason":reason})
    return dispute


@transaction.atomic
def resolve_dispute(dispute,outcome,reason,reference,actor,token):
    StudentProfile.objects.select_for_update().get(pk=dispute.payment.student_id)
    PaymentRequest.objects.select_for_update().get(pk=dispute.payment_id)
    dispute=PaymentDispute.objects.select_for_update().get(pk=dispute.pk)
    if outcome not in {"won","lost"} or not reason.strip(): raise ValidationError("Choose a final outcome and record its evidence.")
    if dispute.status!="open":
        if dispute.status!=outcome: raise ValidationError("This dispute already has a different final outcome.")
        return dispute
    if outcome=="won":
        dispute.recovery=record_adjustment(dispute.payment,"recovery",dispute.debit.amount,reference,reason,actor,token,original=dispute.debit)
    dispute.status=outcome;dispute.resolution=reason;dispute.resolved_by=actor;dispute.resolved_at=timezone.now()
    dispute.save(update_fields=["recovery","status","resolution","resolved_by","resolved_at"])
    AuditEvent.objects.create(actor=actor,action="payment_dispute_"+outcome,target=str(dispute.pk))
    return dispute


@transaction.atomic
def evaluate_financial_hold(student,actor=None):
    student=StudentProfile.objects.select_for_update().get(pk=student.pk)
    policy=FinancialHoldPolicy.objects.filter(pk=1).first()
    overdue=Decimal(0);snapshot={};active=False
    if policy and policy.enabled:
        policy.full_clean()
        cutoff=timezone.localdate()-timedelta(days=policy.grace_days)
        outstanding=Decimal(0)
        for invoice in Invoice.objects.filter(student=student):
            outstanding+=invoice.balance
            if PaymentPlan.objects.filter(invoice=invoice).exists():
                overdue+=sum((balance for installment,balance in installment_balances(invoice) if installment.due<cutoff),Decimal(0))
            elif invoice.due<cutoff: overdue+=invoice.balance
        # Unallocated verified payments and other released credits also protect the account.
        ledger_balance=total(LedgerEntry.objects.filter(student=student,released=True))
        unapplied_credit=max(outstanding-ledger_balance,Decimal(0))
        overdue=max(overdue-unapplied_credit,Decimal(0))
        active=overdue>=policy.overdue_threshold
        snapshot={"threshold":str(policy.overdue_threshold),"grace_days":policy.grace_days,"approval_reference":policy.approval_reference}
    hold,created=FinancialHold.objects.get_or_create(student=student)
    changed=hold.active!=active
    hold.active=active;hold.overdue_amount=overdue;hold.policy_snapshot=snapshot;hold.save()
    if changed:
        event=AuditEvent.objects.create(actor=actor,action="financial_hold_placed" if active else "financial_hold_released",target=str(student.pk))
        notify(student.user,"payment","Financial registration hold updated","Your financial registration hold is now active. Contact finance for review." if active else "Your automatic financial registration hold has been released. Other registration requirements still apply.",f"financial-hold:{event.pk}")
    return hold
