from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404,HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .student_support import AdvisorSlot,AdvisorBooking,SupportCase,SupportNote,SuccessPlan,StudentIntervention,AtRiskAlert,StudentAccommodation,advising_students,support_cases
from .advising import AdvisorAssignment
from .registrar import StudentProfile
from .models import Course,Enrollment
from .student_records import AcademicStanding
from .operations import AuditEvent
from .notification_models import notify


@login_required
def support_home(request):
    profile=StudentProfile.objects.filter(user=request.user).first()
    advisor_ids=AdvisorAssignment.objects.filter(student=profile,active=True).values("advisor_id") if profile else []
    slots=AdvisorSlot.objects.filter(advisor_id__in=advisor_ids,active=True,starts__gt=timezone.now()).exclude(bookings__status="booked").order_by("starts")[:100]
    bookings=AdvisorBooking.objects.filter(Q(student__user=request.user)|Q(slot__advisor=request.user,student__in=advising_students(request.user))).select_related("slot","student").order_by("-slot__starts")[:100]
    alerts=AtRiskAlert.objects.filter(advisor=request.user,standing__student__in=advising_students(request.user)).select_related("standing__student").order_by("-created")[:100]
    return render(request,"support_home.html",{"profile":profile,"cases":support_cases(request.user).select_related("student","advisor").order_by("-created")[:100],"slots":slots,"my_slots":AdvisorSlot.objects.filter(advisor=request.user,active=True,ends__gt=timezone.now()).order_by("starts")[:100],"bookings":bookings,"alerts":alerts})


@login_required
@permission_required("academics.view_advisorassignment",raise_exception=True)
def create_slot(request):
    class SlotForm(forms.Form):
        starts=forms.DateTimeField(help_text="Your selected timezone is shown in the portal footer.")
        ends=forms.DateTimeField()
        location=forms.CharField(max_length=300)
    form=SlotForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        if data["starts"]<=timezone.now() or not data["starts"]<data["ends"]<=data["starts"]+timedelta(hours=4): form.add_error(None,"Choose a future slot lasting at most four hours.")
        else:
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                if AdvisorSlot.objects.filter(advisor=request.user,active=True,starts__lt=data["ends"],ends__gt=data["starts"]).exists(): form.add_error(None,"This overlaps another active slot.")
                else:
                    slot=AdvisorSlot.objects.create(advisor=request.user,**data)
                    AuditEvent.objects.create(actor=request.user,action="advisor_slot_created",target=str(slot.pk))
                    return redirect("support_home")
    return render(request,"form.html",{"form":form,"heading":"Offer an advising appointment"})


@login_required
@require_POST
@transaction.atomic
def book_slot(request,pk):
    slot=get_object_or_404(AdvisorSlot.objects.select_for_update(),pk=pk,active=True,starts__gt=timezone.now())
    profile=get_object_or_404(StudentProfile.objects.select_for_update(),user=request.user,status="active")
    if not AdvisorAssignment.objects.filter(student=profile,advisor=slot.advisor,active=True).exists(): raise Http404()
    if slot.bookings.filter(status="booked").exists(): return HttpResponseForbidden("This appointment has been booked.")
    if AdvisorBooking.objects.filter(student=profile,status="booked",slot__starts__lt=slot.ends,slot__ends__gt=slot.starts).exists(): return HttpResponseForbidden("This overlaps your existing appointment.")
    booking=AdvisorBooking.objects.create(slot=slot,student=profile)
    AuditEvent.objects.create(actor=request.user,action="advisor_appointment_booked",target=str(booking.pk))
    notify(slot.advisor,"enrollment","Advising appointment booked","Review your private student support workspace.",f"advisor-booking:{booking.pk}")
    return redirect("support_home")


@login_required
@require_POST
@transaction.atomic
def change_booking(request,pk):
    booking=get_object_or_404(AdvisorBooking.objects.select_for_update(),pk=pk)
    staff=booking.slot.advisor_id==request.user.pk and advising_students(request.user).filter(pk=booking.student_id).exists()
    own=booking.student.user_id==request.user.pk
    if not own and not staff: raise Http404()
    status=request.POST.get("status")
    if booking.status!="booked" or status not in ("cancelled","completed") or (status=="completed" and (not staff or booking.slot.ends>timezone.now())): return HttpResponseForbidden("Invalid appointment update.")
    if not staff and booking.slot.starts<=timezone.now(): return HttpResponseForbidden("Contact your advisor to change a past appointment.")
    booking.status=status; booking.save(update_fields=["status"])
    AuditEvent.objects.create(actor=request.user,action="advisor_appointment_"+status,target=str(pk))
    notify(booking.student.user,"enrollment","Advising appointment updated","Review your private student support workspace.",f"advisor-booking:{pk}:{status}")
    return redirect("support_home")


@login_required
def create_case(request,assignment_pk=None):
    assigned=get_object_or_404(AdvisorAssignment,pk=assignment_pk,advisor=request.user,active=True,student__in=advising_students(request.user)) if assignment_pk else None
    profile=assigned.student if assigned else get_object_or_404(StudentProfile,user=request.user)
    class CaseForm(forms.Form):
        assignment=forms.ModelChoiceField(queryset=AdvisorAssignment.objects.filter(student=profile,active=True).select_related("advisor"),label="Assigned advisor")
        subject=forms.CharField(max_length=200)
        category=forms.ChoiceField(choices=SupportCase._meta.get_field("category").choices)
        description=forms.CharField(max_length=4000,widget=forms.Textarea,help_text="Describe the support needed. Do not include medical evidence or payment-card details.")
    form=CaseForm(request.POST if request.method=="POST" else None)
    if assigned: del form.fields["assignment"]
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            assignment=get_object_or_404(AdvisorAssignment.objects.select_for_update(),pk=assigned.pk if assigned else form.cleaned_data["assignment"].pk,active=True,student=profile)
            case=SupportCase.objects.create(student=profile,advisor=assignment.advisor,**{k:v for k,v in form.cleaned_data.items() if k!="assignment"})
            AuditEvent.objects.create(actor=request.user,action="support_case_opened",target=str(case.pk))
            notify(case.advisor,"enrollment","Student support request","Review your private student support workspace.",f"support-case:{case.pk}")
        return redirect("support_case",pk=case.pk)
    return render(request,"form.html",{"form":form,"heading":"Request student support"})


@login_required
def case_detail(request,pk):
    case=get_object_or_404(support_cases(request.user),pk=pk)
    staff=case.advisor_id==request.user.pk and advising_students(request.user).filter(pk=case.student_id).exists()
    class NoteForm(forms.Form):
        body=forms.CharField(max_length=4000,widget=forms.Textarea)
        shared=forms.BooleanField(required=False,label="Share this note with the student")
    form=NoteForm(request.POST if request.method=="POST" else None)
    if not staff: del form.fields["shared"]
    if request.method=="POST" and form.is_valid():
        note=SupportNote.objects.create(case=case,author=request.user,body=form.cleaned_data["body"],shared=form.cleaned_data.get("shared",True))
        AuditEvent.objects.create(actor=request.user,action="support_note_added",target=str(note.pk))
        return redirect("support_case",pk=pk)
    notes=case.notes.all() if staff else case.notes.filter(shared=True)
    return render(request,"support_case.html",{"case":case,"staff":staff,"notes":notes.select_related("author").order_by("created"),"plans":case.plans.order_by("-created"),"interventions":case.interventions.all() if staff else [],"form":form})


@login_required
@require_POST
def case_status(request,pk):
    with transaction.atomic():
        case=get_object_or_404(SupportCase.objects.select_for_update(),pk=pk,advisor=request.user,student__in=advising_students(request.user))
        status=request.POST.get("status")
        if status not in {"open","working","resolved"}: return HttpResponseForbidden()
        if case.status!=status:
            case.status=status; case.save(update_fields=["status"])
            event=AuditEvent.objects.create(actor=request.user,action="support_case_"+status,target=str(pk))
            notify(case.student.user,"enrollment","Student support case updated","Check your private support case for its current status.",f"support-status:{event.pk}")
    return redirect("support_case",pk=pk)


@login_required
def add_support_action(request,pk,kind):
    case=get_object_or_404(SupportCase,pk=pk,advisor=request.user,student__in=advising_students(request.user))
    if kind=="plan": model=SuccessPlan; fields=["goals","actions","review_on"]
    elif kind=="intervention": model=StudentIntervention; fields=["action","outcome","follow_up","completed"]
    else: raise Http404()
    Form=forms.modelform_factory(model,fields=fields)
    form=Form(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        item=form.save(commit=False); item.case=case; item.author=request.user; item.save()
        AuditEvent.objects.create(actor=request.user,action="support_"+kind+"_recorded",target=str(item.pk))
        return redirect("support_case",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Record success plan" if kind=="plan" else "Record private intervention"})


@login_required
@permission_required("academics.view_advisorassignment",raise_exception=True)
@require_POST
def flag_risk(request):
    for student in advising_students(request.user):
        standing=AcademicStanding.objects.filter(student=student).order_by("-term__ends","-created").first()
        if standing and standing.status=="probation":
            alert,created=AtRiskAlert.objects.get_or_create(standing=standing,advisor=request.user)
            if created:
                AuditEvent.objects.create(actor=request.user,action="academic_risk_flagged",target=str(alert.pk))
                notify(request.user,"enrollment","Academic support review needed","Review standing alerts in your private student support workspace.",f"risk-alert:{alert.pk}")
    return redirect("support_home")


@login_required
@require_POST
def acknowledge_risk(request,pk):
    item=get_object_or_404(AtRiskAlert,pk=pk,advisor=request.user,standing__student__in=advising_students(request.user))
    if not item.acknowledged:
        item.acknowledged=timezone.now(); item.save(update_fields=["acknowledged"])
        AuditEvent.objects.create(actor=request.user,action="academic_risk_acknowledged",target=str(pk))
    return redirect("support_home")


@login_required
def accommodations(request):
    rows=StudentAccommodation.objects.select_related("student","course")
    if not request.user.has_perm("academics.view_studentaccommodation"):
        from django.db.models import Exists,OuterRef
        rows=rows.annotate(enrolled=Exists(Enrollment.objects.filter(student=OuterRef("student__user_id"),course=OuterRef("course_id"),active=True)))
        rows=rows.filter(Q(student__user=request.user)|Q(course__instructor=request.user,enrolled=True,status="approved",starts__lte=timezone.localdate(),ends__gte=timezone.localdate()))
    return render(request,"accommodations.html",{"rows":rows.order_by("-starts")[:200]})


@login_required
@permission_required("academics.add_studentaccommodation",raise_exception=True)
def draft_accommodation(request):
    Form=forms.modelform_factory(StudentAccommodation,fields=["student","course","instructions","starts","ends","approval_reference","exam_extra_minutes","exam_extra_attempts"])
    form=Form(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        item=form.save(commit=False)
        item.exam_extra_minutes=item.exam_extra_minutes or 0; item.exam_extra_attempts=item.exam_extra_attempts or 0
        if item.starts>item.ends: form.add_error(None,"End date precedes start date.")
        elif not Enrollment.objects.filter(student=item.student.user,course=item.course,active=True).exists(): form.add_error(None,"An active course enrollment is required.")
        else:
            item.created_by=request.user; item.save()
            AuditEvent.objects.create(actor=request.user,action="accommodation_drafted",target=str(item.pk))
            return redirect("accommodations")
    return render(request,"form.html",{"form":form,"heading":"Draft functional accommodation"})


@login_required
@permission_required("academics.change_studentaccommodation",raise_exception=True)
@require_POST
@transaction.atomic
def review_accommodation(request,pk):
    item=get_object_or_404(StudentAccommodation.objects.select_for_update(),pk=pk)
    status=request.POST.get("status")
    if status not in {"approved","revoked"} or (status=="approved" and item.status!="draft") or (status=="revoked" and item.status!="approved"): return HttpResponseForbidden()
    if item.student.user_id==request.user.pk: return HttpResponseForbidden("Another authorized staff member must review your accommodation.")
    item.status=status; item.reviewed_by=request.user; item.reviewed_at=timezone.now(); item.save()
    AuditEvent.objects.create(actor=request.user,action="accommodation_"+status,target=str(pk))
    notify(item.student.user,"enrollment","Accommodation decision available","Review your private accommodation record.",f"accommodation:{pk}:{status}")
    return redirect("accommodations")


@login_required
@permission_required("academics.view_advisorassignment",raise_exception=True)
@require_POST
@transaction.atomic
def close_slot(request,pk):
    slot=get_object_or_404(AdvisorSlot.objects.select_for_update(),pk=pk,advisor=request.user)
    slot.active=False; slot.save(update_fields=["active"])
    for booking in slot.bookings.select_for_update().filter(status="booked"):
        booking.status="cancelled"; booking.save(update_fields=["status"])
        notify(booking.student.user,"enrollment","Advising appointment cancelled","Your advisor cancelled this appointment. Review the support workspace for available times.",f"slot-closed:{booking.pk}")
    AuditEvent.objects.create(actor=request.user,action="advisor_slot_closed",target=str(pk))
    return redirect("support_home")


@login_required
def finish_intervention(request,pk):
    item=get_object_or_404(StudentIntervention,pk=pk,case__advisor=request.user,case__student__in=advising_students(request.user))
    class OutcomeForm(forms.Form): outcome=forms.CharField(max_length=4000,widget=forms.Textarea)
    form=OutcomeForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            item=StudentIntervention.objects.select_for_update().get(pk=pk)
            if item.completed: return HttpResponseForbidden("Intervention already completed.")
            item.outcome=form.cleaned_data["outcome"]; item.completed=True; item.save(update_fields=["outcome","completed"])
            AuditEvent.objects.create(actor=request.user,action="intervention_completed",target=str(pk))
        return redirect("support_case",pk=item.case_id)
    return render(request,"form.html",{"form":form,"heading":"Complete intervention"})
