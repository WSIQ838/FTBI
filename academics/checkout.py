from decimal import Decimal
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,redirect
from django.http import HttpResponse,HttpResponseBadRequest,HttpResponseForbidden,Http404
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .registrar import StudentProfile
from .services import LedgerEntry
from .payments import PaymentRequest
from .operations import AuditEvent
from .notification_models import notify
import stripe
from django import forms
from datetime import timedelta


class CheckoutAmountForm(forms.Form):
    amount=forms.DecimalField(required=False,min_value=Decimal("1"),max_digits=10,decimal_places=2)

@login_required
@require_POST
def checkout(request):
    if not settings.FTBI_STRIPE_ENABLED:
        raise Http404()
    student=get_object_or_404(StudentProfile,user=request.user)
    form=CheckoutAmountForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Enter a valid amount of at least USD 1.00.")
    with transaction.atomic():
        student=StudentProfile.objects.select_for_update().get(pk=student.pk)
        balance=LedgerEntry.objects.filter(student=student,released=True).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if balance<=0 or balance>Decimal("100000"):
            return HttpResponseForbidden("No eligible balance.")
        amount=form.cleaned_data["amount"] or balance
        if amount>balance:
            return HttpResponseBadRequest("Payment exceeds the account balance.")
        item=PaymentRequest.objects.filter(student=student,status="pending",reference__startswith="stripe:",created__gt=timezone.now()-timedelta(hours=24)).order_by("pk").first()
        if item and item.amount!=amount:
            return HttpResponse("An online payment is already pending. Complete or wait for that checkout to expire before changing the amount.",status=409)
        if item is None:
            item=PaymentRequest.objects.create(student=student,amount=amount,reference="stripe:initializing")
    stripe.api_key=settings.STRIPE_SECRET_KEY
    try:
        if item.reference!="stripe:initializing":
            session=stripe.checkout.Session.retrieve(item.reference.removeprefix("stripe:"))
            if session.status!="open":
                return HttpResponse("Checkout is no longer open. Finance must reconcile its outcome before another payment.",status=409)
            return redirect(session.url)
        session=stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{"quantity":1,"price_data":{"currency":"usd","unit_amount":int(item.amount*100),"product_data":{"name":"Academic account payment"}}}],
            metadata={"ftbi_payment_id":str(item.pk)},
            success_url=settings.FTBI_PUBLIC_ORIGIN+reverse("payment_portal"),
            cancel_url=settings.FTBI_PUBLIC_ORIGIN+reverse("payment_portal"),
            idempotency_key="ftbi-payment-"+str(item.pk),
        )
    except stripe.StripeError:
        return HttpResponse("Payment service unavailable. Contact finance.",status=503)
    with transaction.atomic():
        StudentProfile.objects.select_for_update().get(pk=item.student_id)
        locked=PaymentRequest.objects.select_for_update().get(pk=item.pk)
        locked.reference="stripe:"+session.id
        locked.save(update_fields=["reference"])
    return redirect(session.url)

@csrf_exempt
@require_POST
def webhook(request):
    if not settings.FTBI_STRIPE_ENABLED:
        raise Http404()
    try:
        event=stripe.Webhook.construct_event(request.body,request.headers.get("Stripe-Signature",""),settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError,stripe.SignatureVerificationError):
        return HttpResponseBadRequest("Invalid event.")
    if event["type"]!="checkout.session.completed":
        return HttpResponse(status=200)
    session=event["data"]["object"]
    if session.get("payment_status")!="paid":
        return HttpResponse(status=200)
    try:
        pk=int(session.get("metadata",{}).get("ftbi_payment_id",""))
    except (ValueError,TypeError):
        return HttpResponseBadRequest("Missing payment reference.")
    with transaction.atomic():
        student_id=PaymentRequest.objects.filter(pk=pk).values_list("student_id",flat=True).first()
        if student_id is not None:
            StudentProfile.objects.select_for_update().get(pk=student_id)
        item=PaymentRequest.objects.select_for_update().filter(pk=pk).first()
        if item is None:
            return HttpResponseBadRequest("Unknown payment.")
        if item.reference=="stripe:initializing":
            return HttpResponse(status=503)
        if item.reference!="stripe:"+session["id"] or session.get("currency")!="usd" or session.get("amount_total")!=int(item.amount*100):
            return HttpResponseBadRequest("Payment mismatch.")
        if item.status=="verified":
            return HttpResponse(status=200)
        if item.status!="pending":
            return HttpResponse(status=409)
        item.ledger=LedgerEntry.objects.create(student=item.student,description="Online payment "+session["id"][:100],amount=-item.amount,posted=timezone.localdate(),released=True)
        item.status="verified"
        item.save(update_fields=["status","ledger"])
        AuditEvent.objects.create(action="stripe_payment_verified",target=str(item.pk))
        notify(item.student.user,"payment","Payment confirmed","An online payment has been credited to your account. View the private receipt in Payments.",f"payment-confirmed:{item.pk}")
    return HttpResponse(status=200)
