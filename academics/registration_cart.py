"""All-or-nothing registration for already validated concurrent corequisites."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.utils import timezone
from .models import Enrollment
from .registrar import RegistrationWindow,StudentProfile
from .prerequisites import WaitlistEntry,prerequisites_met
from .student_records import WithdrawalRequest
from .finance_adjustments import evaluate_financial_hold
from .operations import AuditEvent
from .notification_models import notify


@transaction.atomic
def register_together(user,window_ids):
    if not 1<=len(window_ids)<=10 or any(type(pk) is not int for pk in window_ids) or len(set(window_ids))!=len(window_ids):
        raise ValidationError("Select between one and ten distinct courses.")
    # Every capacity lock is acquired in the same order, before the student lock.
    windows=list(RegistrationWindow.objects.select_for_update(of=("self",)).filter(pk__in=window_ids).select_related("course").order_by("pk"))
    if len(windows)!=len(window_ids): raise ValidationError("A selected registration window no longer exists.")
    profile=StudentProfile.objects.select_for_update().filter(user=user,status="active",registration_hold=False).first()
    if not user.is_active or not profile: raise ValidationError("Registration requires an active student account without a hold.")
    if evaluate_financial_hold(profile).active: raise ValidationError("A financial registration hold is active. Contact finance.")
    courses=[window.course for window in windows]
    if len({course.term_id for course in courses})!=1: raise ValidationError("Select courses in the same term.")
    if len({course.code for course in courses})!=len(courses): raise ValidationError("Select only one section of each course code.")
    if Enrollment.objects.filter(student=user,active=True,course__term_id=courses[0].term_id,course__code__in=[course.code for course in courses]).exclude(course__in=courses).exists():
        raise ValidationError("You are already enrolled in another section of a selected course.")
    now=timezone.now();pending=[]
    for window in windows:
        course=window.course
        if not course.published or not window.opens<=now<window.closes: raise ValidationError("A selected course is closed for registration.")
        existing=Enrollment.objects.filter(student=user,course=course).first()
        if existing and WithdrawalRequest.objects.filter(enrollment=existing,status="approved").exists(): raise ValidationError("A selected course was withdrawn. Contact the registrar.")
        if existing and existing.active: continue
        if not prerequisites_met(profile,course,concurrent_courses=courses): raise ValidationError("A selected course has unmet prerequisites or corequisites.")
        first=WaitlistEntry.objects.filter(course=course).first()
        if Enrollment.objects.filter(course=course,active=True).count()>=window.capacity or (first and first.student_id!=profile.pk):
            raise ValidationError("A selected course is full or has an earlier waitlist entry. No courses were registered; use individual registration to join a waitlist.")
        pending.append(course)
    for course in pending:
        Enrollment.objects.update_or_create(student=user,course=course,defaults={"active":True})
        WaitlistEntry.objects.filter(course=course,student=profile).delete()
        event=AuditEvent.objects.create(actor=user,action="course_registered_together",target=str(course.pk))
        notify(user,"enrollment","Enrollment confirmed",f"Enrollment in {course.code} is confirmed.",f"enrollment-cart:{event.pk}")
    return len(pending)


@login_required
def registration_cart(request):
    now=timezone.now()
    class CartForm(forms.Form):
        courses=forms.ModelMultipleChoiceField(queryset=RegistrationWindow.objects.filter(course__published=True,opens__lte=now,closes__gt=now).select_related("course","course__term"),help_text="Choose up to ten courses in one term. All selected courses must have seats and meet prerequisites. Corequisites may be selected together.")
        def clean_courses(self):
            rows=self.cleaned_data["courses"]
            if len(rows)>10: raise forms.ValidationError("Choose at most ten courses.")
            return rows
    form=CartForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try: register_together(request.user,[window.pk for window in form.cleaned_data["courses"]])
        except ValidationError as exc: form.add_error(None,exc)
        else: return redirect("student_record")
    return render(request,"form.html",{"form":form,"heading":"Register related courses together","notice":"This action registers every selected eligible course together. If any course fails validation, no enrollment or waitlist changes are saved."})
