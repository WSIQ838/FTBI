from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils import timezone
from django import forms
from .models import Enrollment
from .prerequisites import WaitlistEntry, prerequisites_met
from .registrar import StudentProfile, RegistrationWindow, Application
from .notification_models import notify

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["program","statement"]

@login_required
def student_record(request):
    profile = StudentProfile.objects.filter(user=request.user).select_related("program").first()
    enrollments = Enrollment.objects.filter(student=request.user).select_related("course","course__term")
    return render(request,"student_record.html",{"profile":profile,"enrollments":enrollments,"waitlist":WaitlistEntry.objects.filter(student=profile).select_related("course") if profile else []})

@login_required
def catalog(request):
    now = timezone.now()
    windows = RegistrationWindow.objects.filter(opens__lte=now,closes__gt=now,course__published=True).select_related("course","course__term")
    return render(request,"catalog.html",{"windows":windows})

@login_required
@require_POST
def register(request, pk):
    with transaction.atomic():
        window = get_object_or_404(RegistrationWindow.objects.select_for_update(),pk=pk)
        profile = StudentProfile.objects.select_for_update().filter(user=request.user,status="active",registration_hold=False).first()
        if not profile:
            return HttpResponseForbidden("Registration requires an active student account without a hold.")
        now = timezone.now()
        if not window.course.published or not window.opens <= now < window.closes:
            return HttpResponseForbidden("Registration is closed.")
        existing = Enrollment.objects.filter(student=request.user,course=window.course).first()
        if existing and existing.active:
            return redirect("student_record")
        if not prerequisites_met(profile,window.course):
            return HttpResponseForbidden("Prerequisites are not satisfied.")
        queue=WaitlistEntry.objects.filter(course=window.course)
        first=queue.first()
        if Enrollment.objects.filter(course=window.course,active=True).count() >= window.capacity or (first and first.student_id != profile.pk):
            WaitlistEntry.objects.get_or_create(course=window.course,student=profile)
            return redirect("student_record")
        enrollment,_=Enrollment.objects.update_or_create(student=request.user,course=window.course,defaults={"active":True})
        from .operations import AuditEvent
        event=AuditEvent.objects.create(actor=request.user,action="course_registered",target=str(window.course_id))
        notify(request.user,"enrollment","Enrollment confirmed",f"Enrollment in {window.course.code} is confirmed.",f"enrollment:{event.pk}")
        queue.filter(student=profile).delete()
    return redirect("student_record")

@login_required
def admissions(request):
    form = ApplicationForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            with transaction.atomic():
                Application.objects.create(applicant=request.user,program=form.cleaned_data["program"],statement=form.cleaned_data["statement"])
            return redirect("admissions")
        except IntegrityError:
            form.add_error("program","An application already exists for this program.")
    return render(request,"admissions.html",{"form":form,"applications":Application.objects.filter(applicant=request.user).select_related("program")})
