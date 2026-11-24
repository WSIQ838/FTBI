import secrets
from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.contrib.auth import get_user_model
from django.shortcuts import render,redirect,get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_POST
from .registrar import Application,StudentProfile
from .operations import AuditEvent

class DecisionForm(forms.Form):
    decision=forms.ChoiceField(choices=[("accepted","Accept"),("rejected","Reject")])

@login_required
@permission_required("academics.change_application",raise_exception=True)
def review_queue(request):
    return render(request,"admission_review.html",{"applications":Application.objects.select_related("applicant","program").order_by("-submitted_at")[:200],"form":DecisionForm()})

@login_required
@permission_required("academics.change_application",raise_exception=True)
@require_POST
def decide(request,pk):
    form=DecisionForm(request.POST)
    if not form.is_valid():
        return HttpResponseForbidden("Invalid decision.")
    with transaction.atomic():
        item=get_object_or_404(Application.objects.select_for_update(),pk=pk)
        if item.status!="pending":
            return HttpResponseForbidden("Decision already recorded.")
        item.status=form.cleaned_data["decision"]
        item.save(update_fields=["status"])
        AuditEvent.objects.create(actor=request.user,action="admission_"+item.status,target=str(item.pk))
    return redirect("admission_review")

@login_required
@permission_required("academics.change_application",raise_exception=True)
@permission_required("academics.add_studentprofile",raise_exception=True)
@require_POST
def activate_student(request,pk):
    with transaction.atomic():
        item=get_object_or_404(Application.objects.select_for_update(),pk=pk,status="accepted")
        user=get_user_model().objects.select_for_update().get(pk=item.applicant_id)
        if not user.is_active or user.is_staff or user.is_superuser:
            return HttpResponseForbidden("Applicant account requires review.")
        if StudentProfile.objects.filter(user=user).exists():
            return HttpResponseForbidden("Student profile already exists.")
        profile=StudentProfile.objects.create(user=user,program=item.program,student_number="S"+secrets.token_hex(10).upper(),admitted_on=timezone.localdate())
        AuditEvent.objects.create(actor=request.user,action="student_activated",target=str(profile.pk))
    return redirect("admission_review")

@login_required
def decision_letter(request,pk):
    item=get_object_or_404(Application,pk=pk,applicant=request.user,status__in=["accepted","rejected"])
    return render(request,"decision_letter.html",{"item":item})
