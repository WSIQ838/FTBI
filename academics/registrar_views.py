from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils import timezone
from django import forms
from .models import Enrollment
from .registrar import StudentProfile, RegistrationWindow, Application

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["program","statement"]

@login_required
def student_record(request):
    profile = StudentProfile.objects.filter(user=request.user).select_related("program").first()
    enrollments = Enrollment.objects.filter(student=request.user).select_related("course","course__term")
    return render(request,"student_record.html",{"profile":profile,"enrollments":enrollments})

@login_required
def catalog(request):
    now = timezone.now()
    windows = RegistrationWindow.objects.filter(opens__lte=now,closes__gt=now,course__published=True).select_related("course","course__term")
    return render(request,"catalog.html",{"windows":windows})

@login_required
@require_POST
def register(request, pk):
    with transaction.atomic():
        profile = StudentProfile.objects.select_for_update().filter(user=request.user,status="active",registration_hold=False).first()
        if not profile:
            return HttpResponseForbidden("Registration requires an active student account without a hold.")
        window = get_object_or_404(RegistrationWindow.objects.select_for_update(),pk=pk)
        now = timezone.now()
        if not window.course.published or not window.opens <= now < window.closes:
            return HttpResponseForbidden("Registration is closed.")
        existing = Enrollment.objects.filter(student=request.user,course=window.course).first()
        if existing and existing.active:
            return redirect("student_record")
        if Enrollment.objects.filter(course=window.course,active=True).count() >= window.capacity:
            return HttpResponseForbidden("Section is full.")
        Enrollment.objects.update_or_create(student=request.user,course=window.course,defaults={"active":True})
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
