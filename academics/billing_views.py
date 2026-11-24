import csv
import uuid
from io import BytesIO
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from reportlab.pdfgen import canvas
from .billing import Invoice, TuitionSchedule, PaymentPlan, issue_invoice, verify_manual_payment, allocate_payment, create_plan, installment_balances, bill_schedule
from .registrar import StudentProfile
from .payments import PaymentRequest
from .services import LedgerEntry


class InvoiceForm(forms.Form):
    student=forms.ModelChoiceField(queryset=StudentProfile.objects.all())
    description=forms.CharField(max_length=200)
    amount=forms.DecimalField(min_value=Decimal("0.01"),max_digits=12,decimal_places=2)
    due=forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    token=forms.UUIDField(widget=forms.HiddenInput)


@login_required
@permission_required("academics.view_invoice",raise_exception=True)
def finance(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    return render(request,"finance.html",{"invoices":Invoice.objects.select_related("student").order_by("-created")[:200],"pending":PaymentRequest.objects.filter(status="pending").exclude(reference__startswith="stripe:").select_related("student")[:200],"schedules":TuitionSchedule.objects.filter(active=True)})


@login_required
@permission_required("academics.add_invoice",raise_exception=True)
def new_invoice(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    form=InvoiceForm(request.POST if request.method=="POST" else None,initial={"token":uuid.uuid4()})
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        invoice,_=issue_invoice(data["student"],data["description"],data["amount"],data["due"],f"manual:{request.user.pk}:{data['token']}",request.user)
        return redirect("invoice",pk=invoice.pk)
    return render(request,"form.html",{"form":form,"heading":"Issue invoice"})


@login_required
def invoices(request):
    student=get_object_or_404(StudentProfile,user=request.user)
    return render(request,"invoices.html",{"invoices":Invoice.objects.filter(student=student).order_by("-created")})


def accessible_invoice(user,pk):
    invoice=get_object_or_404(Invoice.objects.select_related("student__user"),pk=pk)
    if invoice.student.user_id!=user.pk and not (user.is_staff and user.has_perm("academics.view_invoice")):
        raise Http404()
    return invoice


@login_required
def invoice(request,pk):
    item=accessible_invoice(request.user,pk)
    return render(request,"invoice.html",{"invoice":item,"installments":installment_balances(item) if PaymentPlan.objects.filter(invoice=item).exists() else [],"payments":PaymentRequest.objects.filter(student=item.student,status="verified")})


@login_required
@permission_required("academics.change_paymentrequest",raise_exception=True)
@require_POST
def verify_payment(request,pk):
    if not request.user.is_staff: return HttpResponseForbidden()
    payment=get_object_or_404(PaymentRequest,pk=pk)
    try: verify_manual_payment(payment,request.user)
    except ValidationError as error: return HttpResponse("; ".join(error.messages),status=400)
    return redirect("finance")


@login_required
@permission_required("academics.add_paymentallocation",raise_exception=True)
def allocate(request,pk):
    if not request.user.is_staff: return HttpResponseForbidden()
    item=get_object_or_404(Invoice,pk=pk)
    class AllocationForm(forms.Form):
        token=forms.UUIDField(widget=forms.HiddenInput)
        payment=forms.ModelChoiceField(queryset=PaymentRequest.objects.filter(student=item.student,status="verified"))
        amount=forms.DecimalField(min_value=Decimal("0.01"),max_digits=12,decimal_places=2)
    form=AllocationForm(request.POST if request.method=="POST" else None,initial={"token":uuid.uuid4()})
    if request.method=="POST" and form.is_valid():
        try:
            allocate_payment(form.cleaned_data["payment"],item,form.cleaned_data["amount"],request.user,form.cleaned_data["token"])
            return redirect("invoice",pk=pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Allocate verified payment"})


@login_required
@permission_required("academics.add_paymentplan",raise_exception=True)
def plan(request,pk):
    if not request.user.is_staff: return HttpResponseForbidden()
    item=get_object_or_404(Invoice,pk=pk)
    class PlanForm(forms.Form):
        installments=forms.CharField(widget=forms.Textarea,help_text="One installment per line: YYYY-MM-DD,amount. Up to 24 installments; total must equal the invoice.",max_length=2000)
        def clean_installments(self):
            from datetime import date
            lines=self.cleaned_data["installments"].splitlines()
            try:
                result=[(date.fromisoformat(line.split(",")[0].strip()),Decimal(line.split(",")[1].strip())) for line in lines]
                if not 1<=len(result)<=24 or any(len(line.split(","))!=2 for line in lines) or any(not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal("0.01")) for _,amount in result): raise ValueError()
            except (ValueError,IndexError,ArithmeticError): raise forms.ValidationError("Enter valid dates and positive amounts with two decimals.")
            return result
    form=PlanForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            create_plan(item,form.cleaned_data["installments"],request.user)
            return redirect("invoice",pk=pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Approve payment plan"})


@login_required
@permission_required("academics.add_invoice",raise_exception=True)
@require_POST
def run_billing(request,pk):
    if not request.user.is_staff: return HttpResponseForbidden()
    schedule=get_object_or_404(TuitionSchedule,pk=pk,active=True)
    bill_schedule(schedule,request.user)
    return redirect("finance")


@login_required
def receipt(request,pk):
    payment=get_object_or_404(PaymentRequest.objects.select_related("student__user"),pk=pk,status="verified")
    if payment.student.user_id!=request.user.pk and not (request.user.is_staff and request.user.has_perm("academics.view_paymentrequest")):
        raise Http404()
    buffer=BytesIO(); pdf=canvas.Canvas(buffer)
    pdf.setTitle("Payment receipt")
    for y,text in [(790,"FTBI payment receipt"),(760,f"Receipt: {payment.pk}"),(735,f"Student: {payment.student.student_number}"),(710,f"Amount: USD {payment.amount:.2f}"),(685,f"Received: {payment.created.date()}"),(660,"Status: verified")]:
        pdf.drawString(50,y,text)
    pdf.save()
    response=HttpResponse(buffer.getvalue(),content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="receipt-{payment.pk}.pdf"'
    response["Cache-Control"]="private, no-store"
    return response


@login_required
@permission_required(("academics.view_invoice","academics.view_paymentrequest","academics.view_ledgerentry"),raise_exception=True)
def reconciliation(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    response=HttpResponse(content_type="text/csv")
    response["Content-Disposition"]='attachment; filename="financial-reconciliation.csv"'
    response["Cache-Control"]="private, no-store"
    writer=csv.writer(response)
    writer.writerow(["student_number","released_ledger_balance","invoiced","verified_payments","allocated","unallocated_payment","account_credit"])
    def total(qs): return qs.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    for student in StudentProfile.objects.order_by("pk").iterator():
        balance=total(LedgerEntry.objects.filter(student=student,released=True))
        verified=PaymentRequest.objects.filter(student=student,status="verified")
        from .billing import PaymentAllocation
        paid=total(verified); allocated=total(PaymentAllocation.objects.filter(payment__in=verified))
        number=student.student_number
        if number.lstrip().startswith(("=","+","-","@")): number="'"+number
        writer.writerow([number,balance,total(Invoice.objects.filter(student=student)),paid,allocated,paid-allocated,max(-balance,Decimal(0))])
    return response
