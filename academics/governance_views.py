from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .registrar import StudentProfile
from .governance import InstitutionPolicy,PolicyRevision,PolicyReview,PolicyAcknowledgment,DemographicResponse,propose_revision,decide_policy,withdraw_policy,active_collection,save_demographics,withdraw_demographics,demographic_counts
from .operations import AuditEvent


def governance_staff(user): return user.is_staff and user.has_perm("academics.view_policyrevision")


def private(response):
    response["Cache-Control"]="private, no-store"
    return response


@login_required
def policies(request):
    current=[revision for policy in InstitutionPolicy.objects.order_by("code") if (revision:=policy.current_revision())]
    pending=PolicyRevision.objects.filter(review__isnull=True).select_related("policy","author").order_by("created")[:200] if governance_staff(request.user) else []
    return private(render(request,"policies.html",{"current":current,"pending":pending,"documents":InstitutionPolicy.objects.all() if governance_staff(request.user) else []}))


@login_required
def policy_detail(request,pk):
    revision=get_object_or_404(PolicyRevision,pk=pk)
    current=revision.policy.current_revision()
    if (not current or current.pk!=revision.pk) and not governance_staff(request.user): raise PermissionDenied()
    return private(render(request,"policy_detail.html",{"revision":revision,"effective":bool(current and current.pk==revision.pk),"acknowledged":PolicyAcknowledgment.objects.filter(revision=revision,user=request.user).exists()}))


@login_required
@permission_required("academics.add_policyrevision",raise_exception=True)
def propose(request,pk):
    if not request.user.is_staff: raise PermissionDenied()
    policy=get_object_or_404(InstitutionPolicy,pk=pk)
    class ProposalForm(forms.Form):
        body=forms.CharField(max_length=12000,widget=forms.Textarea,label="Complete policy text")
        configuration=forms.JSONField(required=False,max_length=40000,widget=forms.Textarea,help_text="Demographic policy only: approved coded questions. See governance manual for the exact schema.")
        effective_from=forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
        expires=forms.DateField(required=False,widget=forms.DateInput(attrs={"type":"date"}))
    form=ProposalForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            revision=propose_revision(policy,request.user,data["body"],data["configuration"] or {},data["effective_from"],data["expires"])
            return redirect("policy_detail",pk=revision.pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Propose new version: "+policy.title})


@login_required
@permission_required("academics.approve_institution_policy",raise_exception=True)
def review(request,pk):
    if not governance_staff(request.user): raise PermissionDenied()
    revision=get_object_or_404(PolicyRevision,pk=pk)
    class ReviewForm(forms.Form):
        decision=forms.ChoiceField(choices=[("approve","Approve"),("reject","Reject")])
        authority=forms.CharField(max_length=200,label="Institutional authority / approval reference")
        reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReviewForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            decide_policy(revision,request.user,form.cleaned_data["decision"]=="approve",form.cleaned_data["reason"],form.cleaned_data["authority"])
            return redirect("policy_detail",pk=pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Independent policy review"})


@login_required
@permission_required("academics.approve_institution_policy",raise_exception=True)
def withdraw(request,pk):
    if not governance_staff(request.user): raise PermissionDenied()
    revision=get_object_or_404(PolicyRevision,pk=pk)
    class WithdrawalForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=WithdrawalForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            withdraw_policy(revision,request.user,form.cleaned_data["reason"])
            return redirect("policies")
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Withdraw policy version","notice":"Withdrawal stops this version from authorizing demographic collection. It does not silently reactivate an older approved version."})


@login_required
@require_POST
def acknowledge(request,pk):
    revision=get_object_or_404(PolicyRevision,pk=pk)
    current=revision.policy.current_revision()
    if not current or current.pk!=revision.pk: raise PermissionDenied("Acknowledge only the currently effective version.")
    _,created=PolicyAcknowledgment.objects.get_or_create(revision=revision,user=request.user)
    if created: AuditEvent.objects.create(actor=request.user,action="policy_acknowledged",target=str(revision.pk))
    return redirect("policy_detail",pk=pk)


@login_required
def demographics(request):
    student=get_object_or_404(StudentProfile,user=request.user)
    existing=DemographicResponse.objects.filter(student=student).first()
    revision=active_collection()
    form=forms.Form(request.POST if request.method=="POST" else None)
    if revision:
        initial=existing.answers if existing and existing.revision_id==revision.pk else {}
        form.fields["revision"]=forms.IntegerField(widget=forms.HiddenInput,initial=revision.pk)
        for question in revision.configuration["questions"]:
            form.fields[question["key"]]=forms.ChoiceField(label=question["label"],choices=[("","Leave unanswered")]+[(choice["code"],choice["label"]) for choice in question["choices"]],required=False,initial=initial.get(question["key"],""))
        form.fields["consent"]=forms.BooleanField(label="I choose to provide these optional answers under the displayed policy")
    if request.method=="POST":
        if not revision: return HttpResponse("Optional collection is not currently authorized.",status=403)
        if form.is_valid():
            if form.cleaned_data["revision"]!=revision.pk: form.add_error(None,"Policy changed. Review the current version before submitting.")
            else:
                answers={q["key"]:form.cleaned_data[q["key"]] for q in revision.configuration["questions"] if form.cleaned_data[q["key"]]}
                try:
                    save_demographics(student,revision,answers)
                    return redirect("demographics")
                except ValidationError as error: form.add_error(None,error)
    return private(render(request,"demographics.html",{"form":form,"revision":revision,"has_response":existing is not None}))


@login_required
@require_POST
def withdraw_answers(request):
    withdraw_demographics(get_object_or_404(StudentProfile,user=request.user))
    return redirect("demographics")


@login_required
@permission_required("academics.view_demographic_aggregates",raise_exception=True)
def demographic_report(request):
    return private(render(request,"demographic_report.html",{"panels":demographic_counts(request.user)}))
