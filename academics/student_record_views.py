from .institution import institution_name
from decimal import Decimal
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import inlineformset_factory
from django.http import HttpResponseForbidden,HttpResponse,JsonResponse,Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Enrollment,Term
from .registrar import StudentProfile,RegistrationWindow
from .student_records import WithdrawalWindow,WithdrawalRequest,GradingScale,AcademicStanding,EmergencyContact,EnrollmentVerification,standing_for
from .services import FinalGrade
from .operations import AuditEvent
from .notification_models import notify


@login_required
@transaction.atomic
def request_withdrawal(request,pk):
    enrollment=get_object_or_404(Enrollment.objects.select_for_update(),pk=pk,student=request.user,active=True)
    window=WithdrawalWindow.objects.filter(course=enrollment.course).first()
    if not window or not window.opens<=timezone.now()<window.closes:
        return HttpResponseForbidden("The withdrawal request window is closed. Contact the registrar.")
    class WithdrawalForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=WithdrawalForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        item,created=WithdrawalRequest.objects.get_or_create(enrollment=enrollment,defaults={"reason":form.cleaned_data["reason"]})
        if created: AuditEvent.objects.create(actor=request.user,action="withdrawal_requested",target=str(item.pk))
        return redirect("student_record")
    return render(request,"form.html",{"form":form,"heading":"Request course withdrawal"})


@login_required
@permission_required("academics.change_withdrawalrequest",raise_exception=True)
def withdrawals(request):
    return render(request,"withdrawals.html",{"requests":WithdrawalRequest.objects.select_related("enrollment__student","enrollment__course").order_by("status","requested")[:200]})


@login_required
@permission_required(("academics.change_withdrawalrequest","academics.change_enrollment","academics.add_finalgrade"),raise_exception=True)
@require_POST
@transaction.atomic
def decide_withdrawal(request,pk):
    item=get_object_or_404(WithdrawalRequest,pk=pk)
    window=RegistrationWindow.objects.select_for_update().filter(course=item.enrollment.course).first()
    student=get_object_or_404(StudentProfile.objects.select_for_update(),user=item.enrollment.student)
    enrollment=Enrollment.objects.select_for_update().get(pk=item.enrollment_id)
    item=WithdrawalRequest.objects.select_for_update().get(pk=pk)
    decision=request.POST.get("decision")
    if item.status!="pending" or decision not in ("approved","denied"): return HttpResponseForbidden("Invalid or already reviewed request.")
    if decision=="approved":
        from .withdrawal_appeals import apply_withdrawal
        try: apply_withdrawal(enrollment,student,window)
        except ValidationError as exc: return HttpResponseForbidden(exc.messages[0])
    item.status=decision; item.reviewed_by=request.user; item.reviewed_at=timezone.now(); item.save()
    AuditEvent.objects.create(actor=request.user,action="withdrawal_"+decision,target=str(pk))
    notify(student.user,"enrollment","Withdrawal decision available","Your course withdrawal request has been reviewed. Check your academic record.",f"withdrawal:{pk}:{decision}")
    return redirect("withdrawal_queue")


@login_required
def emergency_contacts(request):
    student=get_object_or_404(StudentProfile,user=request.user)
    FormSet=inlineformset_factory(StudentProfile,EmergencyContact,fields=["name","relationship","phone","email"],extra=1,max_num=3,validate_max=True)
    forms_set=FormSet(request.POST if request.method=="POST" else None,instance=student)
    if request.method=="POST" and forms_set.is_valid(): forms_set.save(); return redirect("emergency_contacts")
    return render(request,"emergency_contacts.html",{"forms_set":forms_set})


@login_required
def personal_export(request):
    from .models import Submission
    from .services import LedgerEntry
    student=get_object_or_404(StudentProfile,user=request.user)
    data={"format":"ftbi-personal-record-v1","exported_at":timezone.now(),"account":{"username":request.user.username,"first_name":request.user.first_name,"last_name":request.user.last_name,"email":request.user.email},"student":{"number":student.student_number,"program":student.program.name,"status":student.status,"admitted_on":student.admitted_on},"enrollments":list(Enrollment.objects.filter(student=request.user).values("course__code","course__title","course__term__name","active")),"released_grades":list(FinalGrade.objects.filter(student=student,released=True).values("course__code","letter","credits_earned","quality_points")),"released_ledger":list(LedgerEntry.objects.filter(student=student,released=True).values("description","amount","posted")),"submissions":list(Submission.objects.filter(student=request.user).values("assignment__title","body","submitted_at","grade","feedback")),"emergency_contacts":list(student.emergency_contacts.values("name","relationship","phone","email")),"status_history":list(student.status_history.values("previous","current","created")),"scope_notice":"Portal-visible records only. Attachments, private staff notes and institutional audit logs are excluded; contact the registrar for a complete reviewed records request."}
    response=JsonResponse(data); response["Content-Disposition"]='attachment; filename="my-ftbi-records.json"'; response["Cache-Control"]="private, no-store"
    AuditEvent.objects.create(actor=request.user,action="personal_records_exported",target=str(student.pk))
    return response


@login_required
@permission_required("academics.add_academicstanding",raise_exception=True)
def calculate_standing(request):
    class StandingForm(forms.Form):
        student=forms.ModelChoiceField(queryset=StudentProfile.objects.all())
        term=forms.ModelChoiceField(queryset=Term.objects.all())
    form=StandingForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            record=standing_for(form.cleaned_data["student"],form.cleaned_data["term"],request.user)
            AuditEvent.objects.create(actor=request.user,action="academic_standing_calculated",target=str(record.pk))
            return redirect("academic_standing")
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Calculate academic standing"})


@login_required
def academic_standing(request):
    rows=AcademicStanding.objects.select_related("student","term").order_by("-created")
    if not request.user.has_perm("academics.view_academicstanding"): rows=rows.filter(student__user=request.user)
    return render(request,"academic_standing.html",{"rows":rows[:200]})


@login_required
@permission_required("academics.add_finalgrade",raise_exception=True)
def scaled_grade(request,pk):
    enrollment=get_object_or_404(Enrollment.objects.select_related("course","student"),pk=pk)
    student=get_object_or_404(StudentProfile,user=enrollment.student)
    scale=GradingScale.objects.filter(program=student.program,active=True).first()
    if not scale: return HttpResponseForbidden("An approved grading scale must be active.")
    class ScoreForm(forms.Form): score=forms.DecimalField(min_value=0,max_value=100,decimal_places=2)
    form=ScoreForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            StudentProfile.objects.select_for_update().get(pk=student.pk)
            if FinalGrade.objects.filter(student=student,course=enrollment.course).exists(): return HttpResponseForbidden("A grade already exists. Use the registrar correction process.")
            entry=scale.grade(form.cleaned_data["score"])
            grade=FinalGrade.objects.create(student=student,course=enrollment.course,letter=entry["letter"],quality_points=Decimal(str(entry["points"])),credits_earned=enrollment.course.credits if entry["passing"] else 0,released=False)
            AuditEvent.objects.create(actor=request.user,action="scaled_final_grade_drafted",target=str(grade.pk))
        return redirect("final_grade_queue")
    return render(request,"form.html",{"form":form,"heading":"Draft final grade using "+scale.name})


@login_required
@permission_required(("academics.view_enrollment","academics.view_finalgrade"),raise_exception=True)
def final_grade_queue(request):
    return render(request,"final_grade_queue.html",{"enrollments":Enrollment.objects.filter(student__student_profile__isnull=False).select_related("student","course").order_by("pk")[:200],"drafts":FinalGrade.objects.filter(released=False).select_related("student","course")[:200]})


@login_required
@permission_required("academics.change_finalgrade",raise_exception=True)
@require_POST
@transaction.atomic
def release_final_grade(request,pk):
    grade=get_object_or_404(FinalGrade.objects.select_for_update(),pk=pk)
    if not grade.released:
        try: grade.full_clean()
        except ValidationError: return HttpResponse("The draft grade is invalid. Correct it before release.",status=400)
        grade.released=True; grade.save(update_fields=["released"])
        AuditEvent.objects.create(actor=request.user,action="final_grade_released",target=str(pk))
    return redirect("final_grade_queue")


@login_required
@require_POST
@transaction.atomic
def issue_enrollment_letter(request):
    student=get_object_or_404(StudentProfile,user=request.user)
    rows=list(Enrollment.objects.filter(student=request.user,active=True).values("course__code","course__title","course__term__name"))
    if not rows: return HttpResponseForbidden("No active enrollments to verify.")
    from .enrollment_letters import template_snapshot
    try: template=template_snapshot()
    except ValidationError: return HttpResponse("The enrollment letter template is invalid. Contact the registrar.",status=400)
    record=EnrollmentVerification.objects.create(student=student,snapshot={"institution":institution_name(),"name":request.user.get_full_name() or request.user.username,"program":student.program.name,"student_number":student.student_number,"enrollments":rows,"template":template})
    AuditEvent.objects.create(actor=request.user,action="enrollment_letter_issued",target=str(record.identifier))
    return redirect("enrollment_letter",identifier=record.identifier)


@login_required
def enrollment_letter(request,identifier):
    record=get_object_or_404(EnrollmentVerification,identifier=identifier)
    if record.student.user_id!=request.user.pk and not request.user.has_perms(["academics.view_enrollmentverification","academics.view_studentprofile"]): raise Http404()
    from .enrollment_letters import render_letter
    response=HttpResponse(render_letter(record.snapshot,record.identifier,record.issued),content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="enrollment-verification.pdf"'
    response["Cache-Control"]="private, no-store"
    return response
