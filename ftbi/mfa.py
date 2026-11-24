import base64
import secrets
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

class PasswordForm(forms.Form):
    password=forms.CharField(widget=forms.PasswordInput,strip=False)

class TokenForm(forms.Form):
    token=forms.RegexField(regex=r"^[0-9]{6}$",max_length=6,label="Authenticator code")

class MFAGate:
    def __init__(self,get_response):
        self.get_response=get_response
    def __call__(self,request):
        if request.user.is_authenticated:
            exempt={reverse("mfa_setup"),reverse("mfa_verify"),reverse("logout"),reverse("mfa_recover")}
            if request.path_info not in exempt and not request.user.is_verified():
                has_device=TOTPDevice.objects.filter(user=request.user,confirmed=True).exists()
                required=settings.FTBI_REQUIRE_MFA or (settings.FTBI_REQUIRE_STAFF_MFA and request.user.is_staff)
                if has_device or required:
                    return redirect("mfa_verify" if has_device else "mfa_setup")
        return self.get_response(request)

@login_required
def setup(request):
    if TOTPDevice.objects.filter(user=request.user,confirmed=True).exists():
        return redirect("mfa_verify" if not request.user.is_verified() else "dashboard")
    form=PasswordForm(request.POST if request.method=="POST" else None)
    token_form=TokenForm()
    device=TOTPDevice.objects.filter(user=request.user,confirmed=False).first() if request.session.get("mfa_setup_user")==request.user.pk else None
    if request.method=="POST" and request.POST.get("action")=="start":
        if form.is_valid() and request.user.check_password(form.cleaned_data["password"]):
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                if TOTPDevice.objects.filter(user=request.user,confirmed=True).exists():
                    return redirect("mfa_verify")
                TOTPDevice.objects.filter(user=request.user,confirmed=False).delete()
                device=TOTPDevice.objects.create(user=request.user,name="Authenticator",confirmed=False,key=secrets.token_hex(20))
            request.session["mfa_setup_user"]=request.user.pk
            request.session["mfa_setup_device"]=device.pk
            return redirect("mfa_setup")
        form.add_error(None,"Password confirmation failed.")
    elif request.method=="POST" and request.POST.get("action")=="confirm":
        token_form=TokenForm(request.POST)
        if device and token_form.is_valid():
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                locked=TOTPDevice.objects.select_for_update().filter(pk=request.session.get("mfa_setup_device"),user=request.user,confirmed=False).first()
                if locked and not TOTPDevice.objects.filter(user=request.user,confirmed=True).exists() and locked.verify_token(token_form.cleaned_data["token"]):
                    locked.confirmed=True
                    locked.save(update_fields=["confirmed"])
                    otp_login(request,locked)
                    request.session.pop("mfa_setup_user",None)
                    request.session.pop("mfa_setup_device",None)
                    request.session.cycle_key()
                    return redirect("dashboard")
            token_form.add_error(None,"Code invalid or temporarily throttled.")
    secret=base64.b32encode(device.bin_key).decode("ascii") if device and device.pk==request.session.get("mfa_setup_device") else None
    return render(request,"mfa_setup.html",{"form":form,"token_form":token_form,"secret":secret})

@login_required
def verify(request):
    if request.user.is_verified():
        return redirect("dashboard")
    if not TOTPDevice.objects.filter(user=request.user,confirmed=True).exists():
        return redirect("mfa_setup")
    form=TokenForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            device=TOTPDevice.objects.select_for_update().filter(user=request.user,confirmed=True).first()
            if device and device.verify_token(form.cleaned_data["token"]):
                otp_login(request,device)
                request.session.cycle_key()
                return redirect("dashboard")
        form.add_error(None,"Code invalid or temporarily throttled.")
    return render(request,"mfa_verify.html",{"form":form})
