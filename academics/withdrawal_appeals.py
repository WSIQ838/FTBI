from datetime import timedelta
from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.http import HttpResponseForbidden
from django.utils import timezone
from .models import Enrollment
from .registrar import StudentProfile,RegistrationWindow
from .student_records import WithdrawalRequest,WithdrawalWindow,WithdrawalAppeal
from .services import FinalGrade
from .operations import AuditEvent
from .notification_models import notify


def apply_withdrawal(enrollment,student,window):
    if FinalGrade.objects.filter(student=student,course=enrollment.course,released=True).exists():
        raise ValidationError("A released grade exists; use the registrar's grade correction process.")
    enrollment.active=False;enrollment.save(update_fields=["active"])
    FinalGrade.objects.update_or_create(student=student,course=enrollment.course,defaults={"letter":"W","quality_points":None,"credits_earned":0,"released":True})
    if window:
        from .registration_lifecycle import promote_locked
        promote_locked(window)


@login_required
@transaction.atomic
def submit_appeal(request,pk):
    item=get_object_or_404(WithdrawalRequest.objects.select_for_update(of=("self",)),pk=pk,enrollment__student=request.user)
    existing=WithdrawalAppeal.objects.filter(request=item).first()
    if existing: return render(request,"withdrawal_appeal.html",{"item":existing})
    policy=WithdrawalWindow.objects.filter(course=item.enrollment.course).first()
    if item.status!="denied" or not item.reviewed_at or not policy or not policy.appeal_days or not policy.appeal_approval_reference.strip() or timezone.now()>=item.reviewed_at+timedelta(days=policy.appeal_days):
        return HttpResponseForbidden("Appeals are unavailable or the approved appeal window has closed. Contact the registrar.")
    class AppealForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea,help_text="Explain your grounds for review. Do not include medical evidence here.")
    form=AppealForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        appeal=WithdrawalAppeal.objects.create(request=item,reason=form.cleaned_data["reason"],original_decision={"status":item.status,"reason":item.reason,"reviewed_by":item.reviewed_by_id,"reviewed_at":item.reviewed_at.isoformat()},policy_snapshot={"appeal_days":policy.appeal_days,"approval_reference":policy.appeal_approval_reference,"deadline":(item.reviewed_at+timedelta(days=policy.appeal_days)).isoformat()})
        AuditEvent.objects.create(actor=request.user,action="withdrawal_appeal_submitted",target=str(appeal.pk))
        return redirect("withdrawal_appeal",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Appeal withdrawal denial"})


@login_required
@permission_required("academics.change_withdrawalappeal",raise_exception=True)
def appeal_queue(request):
    return render(request,"withdrawal_appeals.html",{"appeals":WithdrawalAppeal.objects.select_related("request__enrollment__course","request__enrollment__student").order_by("status","submitted")[:200]})


@login_required
@permission_required(("academics.change_withdrawalappeal","academics.change_enrollment","academics.add_finalgrade"),raise_exception=True)
def review_appeal(request,pk):
    item=get_object_or_404(WithdrawalAppeal,pk=pk)
    class ReviewForm(forms.Form):
        decision=forms.ChoiceField(choices=[("denied","Uphold denial"),("granted","Grant withdrawal and record W")])
        reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReviewForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            original=item.request
            window=RegistrationWindow.objects.select_for_update().filter(course=original.enrollment.course).first()
            student=get_object_or_404(StudentProfile.objects.select_for_update(),user=original.enrollment.student)
            enrollment=Enrollment.objects.select_for_update().get(pk=original.enrollment_id)
            original=WithdrawalRequest.objects.select_for_update().get(pk=original.pk)
            item=WithdrawalAppeal.objects.select_for_update().get(pk=pk)
            if item.status!="pending" or original.status!="denied": return HttpResponseForbidden("Appeal already reviewed or original decision changed.")
            if request.user.pk in {student.user_id,item.original_decision["reviewed_by"],original.reviewed_by_id}: return HttpResponseForbidden("An independent authorized reviewer must decide this appeal.")
            if form.cleaned_data["decision"]=="granted":
                try: apply_withdrawal(enrollment,student,window)
                except ValidationError as exc: return HttpResponseForbidden(exc.messages[0])
                original.status="approved";original.reviewed_by=request.user;original.reviewed_at=timezone.now();original.save()
            item.status=form.cleaned_data["decision"];item.decision_reason=form.cleaned_data["reason"];item.reviewed_by=request.user;item.reviewed_at=timezone.now();item.save()
            AuditEvent.objects.create(actor=request.user,action="withdrawal_appeal_"+item.status,target=str(pk))
            notify(student.user,"enrollment","Withdrawal appeal decision available","Review your private academic record for the appeal decision.",f"withdrawal-appeal:{pk}:decision")
        return redirect("withdrawal_appeals")
    return render(request,"form.html",{"form":form,"heading":"Review withdrawal appeal","notice":item.reason})
