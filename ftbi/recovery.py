import secrets
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password,check_password
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render,redirect
from django.views.decorators.debug import sensitive_post_parameters
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from academics.recovery_models import RecoveryCode
from academics.passkeys import PasskeyDevice
from academics.operations import AuditEvent
from django.core.cache import cache

class RecoveryForm(forms.Form):
    code=forms.RegexField(regex=r"^[a-fA-F0-9]{24}$",max_length=24)

class ConfirmForm(forms.Form):
    password=forms.CharField(widget=forms.PasswordInput,strip=False)

@login_required
@sensitive_post_parameters("password")
def generate(request):
    if not request.user.is_verified():
        return HttpResponseForbidden("Verify your authenticator first.")
    form=ConfirmForm(request.POST if request.method=="POST" else None)
    codes=None
    if request.method=="POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["password"]):
            form.add_error(None,"Password confirmation failed.")
        else:
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                RecoveryCode.objects.filter(user=request.user).delete()
                codes=[secrets.token_hex(12) for _ in range(8)]
                RecoveryCode.objects.bulk_create([RecoveryCode(user=request.user,digest=make_password(code)) for code in codes])
                AuditEvent.objects.create(actor=request.user,action="recovery_codes_rotated",target="account")
    response=render(request,"recovery_codes.html",{"form":form,"codes":codes})
    response["Cache-Control"]="private, no-store"
    return response

@login_required
@sensitive_post_parameters("code")
def recover(request):
    if request.user.is_verified():
        return redirect("dashboard")
    form=RecoveryForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        key="mfa-recovery:"+str(request.user.pk)
        cache.add(key,0,300)
        try: count=cache.incr(key)
        except ValueError: count=6
        if count>5:
            return HttpResponseForbidden("Too many recovery attempts.")
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            device=TOTPDevice.objects.filter(user=request.user,confirmed=True).first() or PasskeyDevice.objects.filter(user=request.user,confirmed=True).first()
            if device:
                for record in RecoveryCode.objects.select_for_update().filter(user=request.user):
                    if check_password(form.cleaned_data["code"].lower(),record.digest):
                        record.delete()
                        otp_login(request,device)
                        request.session.cycle_key()
                        AuditEvent.objects.create(actor=request.user,action="recovery_code_used",target="account")
                        return redirect("dashboard")
        form.add_error(None,"Invalid or already used recovery code.")
    return render(request,"form.html",{"form":form,"heading":"Use a recovery code"})
