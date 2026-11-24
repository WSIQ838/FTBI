from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.cache import cache
from django.http import Http404,HttpResponse
from django.shortcuts import render,redirect
from django.db import IntegrityError,transaction
import hashlib

class ApplicantForm(UserCreationForm):
    first_name=forms.CharField(max_length=150)
    last_name=forms.CharField(max_length=150)
    class Meta(UserCreationForm.Meta):
        model=get_user_model()
        fields=("username","first_name","last_name")
    def save(self,commit=True):
        user=super().save(commit=False)
        user.first_name=self.cleaned_data["first_name"]
        user.last_name=self.cleaned_data["last_name"]
        # Email ownership is not yet verified: prevent password recovery to
        # an unverified address by storing it only after staff verification.
        user.email=""
        if commit:
            user.save()
        return user

def applicant_signup(request):
    if not settings.FTBI_PUBLIC_ADMISSIONS:
        raise Http404()
    if request.user.is_authenticated:
        return redirect("admissions")
    form=ApplicantForm(request.POST if request.method=="POST" else None)
    if request.method=="POST":
        key="signup:"+hashlib.sha256(request.META.get("REMOTE_ADDR","unknown").encode()).hexdigest()
        cache.add(key,0,3600)
        if cache.incr(key)>5:
            return HttpResponse("Too many registration attempts.",status=429)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                return redirect("login")
            except IntegrityError:
                form.add_error("username","Choose another username.")
    return render(request,"applicant_signup.html",{"form":form})
