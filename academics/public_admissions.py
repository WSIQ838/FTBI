from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import Http404,HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.db import IntegrityError,transaction
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
import hashlib
import logging
import uuid
from .admissions_support import ApplicantActivation

class ActivationToken(PasswordResetTokenGenerator):
    def _make_hash_value(self,user,timestamp):
        nonce=ApplicantActivation.objects.filter(user=user,consumed=False).values_list("nonce",flat=True).first()
        return super()._make_hash_value(user,timestamp)+str(user.is_active)+str(nonce)

token_generator=ActivationToken()

class ApplicantForm(UserCreationForm):
    first_name=forms.CharField(max_length=150)
    last_name=forms.CharField(max_length=150)
    email=forms.EmailField()
    class Meta(UserCreationForm.Meta):
        model=get_user_model()
        fields=("username","first_name","last_name","email")
    def save(self,commit=True):
        user=super().save(commit=False)
        user.email=self.cleaned_data["email"]
        user.is_active=False
        if commit: user.save()
        return user

@sensitive_post_parameters("password1","password2")
def applicant_signup(request):
    if not settings.FTBI_PUBLIC_ADMISSIONS:
        raise Http404()
    if not settings.SMTP_CONFIGURED or not settings.FTBI_ADMISSIONS_ORIGIN:
        return HttpResponse("Applicant signup is temporarily unavailable.",status=503)
    if request.user.is_authenticated:
        return redirect("admissions")
    form=ApplicantForm(request.POST if request.method=="POST" else None)
    if request.method=="POST":
        key="signup:"+hashlib.sha256(request.META.get("REMOTE_ADDR","unknown").encode()).hexdigest()
        cache.add(key,0,3600)
        try: count=cache.incr(key)
        except ValueError: count=6
        if count>5:
            return HttpResponse("Too many registration attempts.",status=429)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user=form.save()
                    ApplicantActivation.objects.create(user=user)
                    # No account becomes active until email ownership is proven.
                    url=settings.FTBI_ADMISSIONS_ORIGIN+reverse("applicant_activate",args=[user.pk,token_generator.make_token(user)])
                    send_mail("Confirm your applicant account","Confirm your email by visiting "+url+" . If you did not request this account, ignore this message.",settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=False)
                return render(request,"applicant_pending.html")
            except IntegrityError:
                form.add_error("username","Choose another username.")
            except Exception:
                logging.getLogger(__name__).warning("Applicant activation email failed")
                form.add_error(None,"Registration could not be completed. Contact admissions.")
    return render(request,"applicant_signup.html",{"form":form})

def activate(request,pk,token):
    if not settings.FTBI_PUBLIC_ADMISSIONS:
        raise Http404()
    with transaction.atomic():
        user=get_object_or_404(get_user_model().objects.select_for_update(),pk=pk,is_active=False,is_staff=False,is_superuser=False)
        marker=get_object_or_404(ApplicantActivation,user=user,consumed=False)
        if not token_generator.check_token(user,token):
            raise Http404()
        if request.method=="POST":
            user.is_active=True
            user.save(update_fields=["is_active"])
            marker.consumed=True; marker.save(update_fields=["consumed"])
            return redirect("login")
    response=render(request,"applicant_activate.html")
    response["Referrer-Policy"]="no-referrer"
    response["Cache-Control"]="no-store"
    return response


def resend_activation(request):
    if not settings.FTBI_PUBLIC_ADMISSIONS: raise Http404()
    if not settings.SMTP_CONFIGURED or not settings.FTBI_ADMISSIONS_ORIGIN: return HttpResponse("Activation recovery is temporarily unavailable.",status=503)
    class RecoveryForm(forms.Form):
        username=forms.CharField(max_length=150)
        email=forms.EmailField()
    form=RecoveryForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        key="activation-resend:"+hashlib.sha256(request.META.get("REMOTE_ADDR","unknown").encode()).hexdigest()
        cache.add(key,0,3600)
        try: count=cache.incr(key)
        except ValueError: count=4
        if count>3: return HttpResponse("Too many recovery requests. Try later.",status=429)
        with transaction.atomic():
            user=get_user_model().objects.select_for_update().filter(username=form.cleaned_data["username"],email__iexact=form.cleaned_data["email"],is_active=False,is_staff=False,is_superuser=False).first()
            if user and (hasattr(user,"student_profile") or user.groups.exists()): user=None
            marker=ApplicantActivation.objects.filter(user=user,consumed=False).first() if user else None
            if marker:
                marker.nonce=uuid.uuid4(); marker.save()
                url=settings.FTBI_ADMISSIONS_ORIGIN+reverse("applicant_activate",args=[user.pk,token_generator.make_token(user)])
                try: send_mail("Confirm your applicant account","Confirm your email by visiting "+url+" .",settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=False)
                except Exception:
                    logging.getLogger(__name__).warning("Applicant activation recovery email failed")
        return render(request,"activation_recovery_pending.html")
    return render(request,"form.html",{"form":form,"heading":"Recover applicant activation link"})
