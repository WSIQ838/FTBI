from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Enrollment
from .registrar import RegistrationWindow,StudentProfile
from .prerequisites import WaitlistEntry,prerequisites_met
from .operations import AuditEvent

def promote_locked(window):
    now=timezone.now()
    if not window.course.published or not window.opens<=now<window.closes:
        return
    while Enrollment.objects.filter(course=window.course,active=True).count()<window.capacity:
        entry=WaitlistEntry.objects.filter(course=window.course).select_related("student").first()
        if not entry:
            break
        profile=entry.student
        if profile.status!="active" or profile.registration_hold or not profile.user.is_active or not prerequisites_met(profile,window.course):
            # Preserve queue order until registrar resolves an ineligible head.
            break
        Enrollment.objects.update_or_create(student=profile.user,course=window.course,defaults={"active":True})
        AuditEvent.objects.create(actor=profile.user,action="waitlist_promoted",target=str(window.course_id))
        entry.delete()

@login_required
@require_POST
def drop(request,pk):
    with transaction.atomic():
        enrollment=get_object_or_404(Enrollment,pk=pk,student=request.user,active=True)
        window=get_object_or_404(RegistrationWindow.objects.select_for_update(),course=enrollment.course)
        if not window.opens<=timezone.now()<window.closes:
            return HttpResponseForbidden("Add/drop window is closed. Contact registrar.")
        if enrollment.student.submissions.filter(assignment__course=enrollment.course).exists() or enrollment.student.attempt_set.filter(quiz__course=enrollment.course).exists():
            return HttpResponseForbidden("Coursework already exists. Contact registrar.")
        enrollment.active=False
        enrollment.save(update_fields=["active"])
        AuditEvent.objects.create(actor=request.user,action="course_dropped",target=str(enrollment.course_id))
        promote_locked(window)
    return redirect("student_record")

@login_required
@require_POST
def leave_waitlist(request,pk):
    with transaction.atomic():
        entry=get_object_or_404(WaitlistEntry,pk=pk,student__user=request.user)
        window=get_object_or_404(RegistrationWindow.objects.select_for_update(),course=entry.course)
        entry.delete()
        promote_locked(window)
    return redirect("student_record")
