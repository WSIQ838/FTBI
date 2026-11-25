import csv
from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.http import HttpResponse,Http404,HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .admissions_support import ApplicationReviewer,ApplicationNote,AdmissionInterview,reviewable
from .registrar import Application,StudentProfile
from .documents import PrivateDocument
from .operations import AuditEvent
from .notification_models import notify


@login_required
def application_details(request,pk):
    application=get_object_or_404(Application,pk=pk)
    staff=reviewable(request.user).filter(pk=pk).exists()
    if application.applicant_id!=request.user.pk and not staff: raise Http404()
    return render(request,"application_details.html",{"application":application,"reviewing":staff,"documents":PrivateDocument.objects.filter(application=application),"notes":application.review_notes.select_related("author") if staff else [],"interviews":application.interviews.select_related("interviewer").order_by("starts")})


@login_required
@permission_required("academics.add_applicationnote",raise_exception=True)
def application_note(request,pk):
    application=get_object_or_404(reviewable(request.user),pk=pk)
    class NoteForm(forms.Form): body=forms.CharField(max_length=4000,widget=forms.Textarea)
    form=NoteForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        note=ApplicationNote.objects.create(application=application,author=request.user,body=form.cleaned_data["body"])
        AuditEvent.objects.create(actor=request.user,action="admission_note_added",target=str(note.pk))
        return redirect("application_details",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Add private review note"})


@login_required
@permission_required("academics.change_applicationreviewer",raise_exception=True)
def assign_reviewer(request,pk):
    application=get_object_or_404(Application,pk=pk)
    class AssignmentForm(forms.Form): reviewer=forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True,is_staff=True))
    form=AssignmentForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        reviewer=form.cleaned_data["reviewer"]
        if not reviewer.has_perm("academics.change_application"): form.add_error("reviewer","Reviewer needs admissions review permission.")
        else:
            with transaction.atomic():
                Application.objects.select_for_update().get(pk=pk)
                ApplicationReviewer.objects.update_or_create(application=application,defaults={"reviewer":reviewer,"assigned_by":request.user})
                AuditEvent.objects.create(actor=request.user,action="application_reviewer_assigned",target=str(pk))
            return redirect("application_details",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Assign application reviewer"})


@login_required
@permission_required("academics.add_admissioninterview",raise_exception=True)
def schedule_interview(request,pk):
    application=get_object_or_404(reviewable(request.user),pk=pk,status="pending")
    class InterviewForm(forms.Form):
        interviewer=forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_staff=True,is_active=True))
        starts=forms.DateTimeField(help_text="Date and time in your selected timezone, shown in the portal footer.")
        ends=forms.DateTimeField()
        location=forms.CharField(max_length=300)
    form=InterviewForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        values=form.cleaned_data
        if not values["interviewer"].has_perm("academics.change_application"): form.add_error("interviewer","Interviewer needs admissions review permission.")
        elif values["starts"]<=timezone.now() or not values["starts"]<values["ends"]<=values["starts"]+timedelta(hours=8): form.add_error(None,"Choose a future interview lasting at most eight hours.")
        else:
            with transaction.atomic():
                locked=Application.objects.select_for_update().get(pk=pk)
                if locked.status!="pending": return HttpResponseForbidden("Application is closed.")
                list(get_user_model().objects.select_for_update().filter(pk__in=[values["interviewer"].pk,application.applicant_id]).order_by("pk"))
                conflicts=AdmissionInterview.objects.filter(status="scheduled",starts__lt=values["ends"],ends__gt=values["starts"])
                if conflicts.filter(interviewer=values["interviewer"]).exists() or conflicts.filter(application__applicant=application.applicant).exists(): form.add_error(None,"The interviewer or applicant already has an overlapping interview.")
                else:
                    item=AdmissionInterview.objects.create(application=application,created_by=request.user,**values)
                    AuditEvent.objects.create(actor=request.user,action="admission_interview_scheduled",target=str(item.pk))
                    notify(application.applicant,"admissions","Admissions interview scheduled","Check your private application details for your interview time and location.",f"interview:{item.pk}")
                    return redirect("application_details",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Schedule admissions interview"})


@login_required
@permission_required("academics.change_admissioninterview",raise_exception=True)
@require_POST
def cancel_interview(request,pk):
    with transaction.atomic():
        item=get_object_or_404(AdmissionInterview.objects.select_for_update(),pk=pk,application__in=reviewable(request.user))
        if item.status=="scheduled":
            item.status="cancelled"; item.save(update_fields=["status"])
            AuditEvent.objects.create(actor=request.user,action="admission_interview_cancelled",target=str(pk))
            notify(item.application.applicant,"admissions","Admissions interview cancelled","Check your private application details or contact admissions.",f"interview-cancel:{pk}")
    return redirect("application_details",pk=item.application_id)


@login_required
@permission_required(("academics.view_application","academics.view_studentprofile"),raise_exception=True)
def conversion_report(request):
    response=HttpResponse(content_type="text/csv")
    response["Content-Disposition"]='attachment; filename="admissions-conversion.csv"'
    writer=csv.writer(response); writer.writerow(["application_id","program_id","submitted","status","student_record_created","admitted_on"])
    profiles={(p.user_id,p.program_id):p for p in StudentProfile.objects.all()}
    for application in Application.objects.order_by("pk").iterator():
        profile=profiles.get((application.applicant_id,application.program_id))
        writer.writerow([application.pk,application.program_id,application.submitted_at.isoformat(),application.status,bool(profile),profile.admitted_on.isoformat() if profile else ""])
    AuditEvent.objects.create(actor=request.user,action="admissions_conversion_exported",target="aggregate-records")
    return response
