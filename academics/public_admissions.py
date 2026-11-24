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

class ActivationToken(PasswordResetTokenGenerator):
    def _make_hash_value(self,user,timestamp):
        return super()._make_hash_value(user,timestamp)+str(user.is_active)

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
        if not token_generator.check_token(user,token):
            raise Http404()
        if request.method=="POST":
            user.is_active=True
            user.save(update_fields=["is_active"])
            return redirect("login")
    response=render(request,"applicant_activate.html")
    response["Referrer-Policy"]="no-referrer"
    response["Cache-Control"]="no-store"
    return response
