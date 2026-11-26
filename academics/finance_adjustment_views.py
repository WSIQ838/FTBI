import uuid
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404,HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .payments import PaymentRequest
from .registrar import StudentProfile
from .finance_adjustments import FinancialHold,PaymentDispute,record_adjustment,open_dispute,resolve_dispute,net_payment,allocated_payment,evaluate_financial_hold


def can_view_finance(user): return user.is_staff and user.has_perms(["academics.view_paymentrequest","academics.view_paymentadjustment","academics.view_paymentdispute"])


@login_required
def history(request):
    rows=PaymentRequest.objects.filter(status="verified").select_related("student").order_by("-pk")
    staff=can_view_finance(request.user)
    if not staff: rows=rows.filter(student__user=request.user)
    payments=[{"payment":p,"net":net_payment(p),"allocated":allocated_payment(p),"adjustments":p.adjustments.order_by("pk"),"disputes":p.disputes.all()} for p in rows[:200]]
    profile=StudentProfile.objects.filter(user=request.user).first()
    hold=FinancialHold.objects.filter(student=profile).first() if profile else None
    response=render(request,"payment_history.html",{"payments":payments,"finance_access":staff,"hold":hold})
    response["Cache-Control"]="private, no-store"
    return response


class AdjustmentForm(forms.Form):
    amount=forms.DecimalField(min_value=Decimal("0.01"),max_digits=12,decimal_places=2)
    reference=forms.CharField(max_length=160,label="Unique external evidence reference")
    reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    confirmed=forms.BooleanField(label="I have independently confirmed the funds were returned or withheld")
    token=forms.UUIDField(widget=forms.HiddenInput)


@login_required
@permission_required("academics.add_paymentadjustment",raise_exception=True)
def adjust(request,pk,kind):
    if not request.user.is_staff or not can_view_finance(request.user): return HttpResponseForbidden()
    if kind not in {"refund","chargeback"}: raise Http404()
    if kind=="chargeback" and not request.user.has_perm("academics.add_paymentdispute"): return HttpResponseForbidden()
    payment=get_object_or_404(PaymentRequest,pk=pk,status="verified")
    form=AdjustmentForm(request.POST if request.method=="POST" else None,initial={"token":uuid.uuid4()})
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            if kind=="refund": record_adjustment(payment,kind,data["amount"],data["reference"],data["reason"],request.user,data["token"])
            else: open_dispute(payment,data["amount"],data["reference"],data["reason"],request.user,data["token"])
            return redirect("payment_history")
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,"Evidence reference or request is already recorded. Refresh the history before retrying.")
    return render(request,"form.html",{"form":form,"heading":"Record confirmed refund" if kind=="refund" else "Record confirmed withheld funds and open dispute","notice":"This records an already confirmed external transaction. It does not send money or contact a bank. Processor-managed payments require provider reconciliation."})


@login_required
@permission_required(("academics.change_paymentdispute","academics.add_paymentadjustment"),raise_exception=True)
def resolve(request,pk):
    if not can_view_finance(request.user): return HttpResponseForbidden()
    dispute=get_object_or_404(PaymentDispute,pk=pk)
    class ResolutionForm(forms.Form):
        outcome=forms.ChoiceField(choices=[("won","Won: funds actually restored"),("lost","Lost: funds remain withheld")])
        reason=forms.CharField(max_length=2000,widget=forms.Textarea,label="Final decision and evidence")
        reference=forms.CharField(max_length=160,label="Unique restoration reference (required if won)",required=False)
        confirmed=forms.BooleanField(label="I have independently confirmed the final outcome and any restored funds")
        token=forms.UUIDField(widget=forms.HiddenInput)
    form=ResolutionForm(request.POST if request.method=="POST" else None,initial={"token":uuid.uuid4()})
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            resolve_dispute(dispute,data["outcome"],data["reason"],data["reference"],request.user,data["token"])
            return redirect("payment_history")
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,"Evidence reference or request is already recorded. Review the history before retrying.")
    return render(request,"form.html",{"form":form,"heading":"Resolve payment dispute"})


@login_required
@permission_required("academics.change_financialhold",raise_exception=True)
@require_POST
def refresh_holds(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    for student in StudentProfile.objects.order_by("pk").iterator(): evaluate_financial_hold(student,request.user)
    return redirect("finance")
