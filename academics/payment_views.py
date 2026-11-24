from django.contrib.auth.decorators import login_required
from django import forms
from django.shortcuts import render,redirect,get_object_or_404
from django.conf import settings
from .registrar import StudentProfile
from .payments import PaymentRequest

class PaymentForm(forms.ModelForm):
    class Meta:
        model=PaymentRequest
        fields=["amount","reference"]

@login_required
def payment_portal(request):
    student=get_object_or_404(StudentProfile,user=request.user)
    form=PaymentForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        payment=form.save(commit=False)
        payment.student=student
        payment.save()
        return redirect("payment_portal")
    return render(request,"payments.html",{"form":form,"payment_url":settings.FTBI_PAYMENT_URL,"requests":PaymentRequest.objects.filter(student=student).order_by("-created")})
