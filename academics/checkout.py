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
import stripe

@login_required
@require_POST
def checkout(request):
    if not settings.FTBI_STRIPE_ENABLED:
        raise Http404()
    student=get_object_or_404(StudentProfile,user=request.user)
    with transaction.atomic():
        student=StudentProfile.objects.select_for_update().get(pk=student.pk)
        balance=LedgerEntry.objects.filter(student=student,released=True).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if balance<=0 or balance>Decimal("100000"):
            return HttpResponseForbidden("No eligible balance.")
        item=PaymentRequest.objects.create(student=student,amount=balance,reference="stripe:initializing")
    stripe.api_key=settings.STRIPE_SECRET_KEY
    try:
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
        LedgerEntry.objects.create(student=item.student,description="Online payment "+session["id"][:100],amount=-item.amount,posted=timezone.localdate(),released=True)
        item.status="verified"
        item.save(update_fields=["status"])
        AuditEvent.objects.create(action="stripe_payment_verified",target=str(item.pk))
    return HttpResponse(status=200)
