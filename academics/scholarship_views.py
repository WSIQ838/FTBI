from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from .registrar import StudentProfile
from .scholarships import ScholarshipFund,ScholarshipApplication,ScholarshipAward,eligibility,submit_application,decide_application,change_award


def staff_access(user): return user.is_staff and user.has_perms(["academics.view_scholarshipapplication","academics.view_scholarshipaward"])


@login_required
def home(request):
    profile=StudentProfile.objects.filter(user=request.user).first()
    staff=staff_access(request.user)
    applications=ScholarshipApplication.objects.select_related("fund","student","award").order_by("-submitted")
    if not staff: applications=applications.filter(student__user=request.user)
    funds=ScholarshipFund.objects.filter(published=True,opens__lte=timezone.now(),closes__gt=timezone.now()).select_related("term","program")
    if profile: funds=funds.filter(Q(program__isnull=True)|Q(program=profile.program))
    rows=[{"fund":fund,"eligibility":eligibility(profile,fund) if profile else None} for fund in funds]
    response=render(request,"scholarships.html",{"funds":rows,"applications":applications[:200],"profile":profile,"scholarship_staff":staff})
    response["Cache-Control"]="private, no-store"
    return response


@login_required
def apply(request,pk):
    student=get_object_or_404(StudentProfile,user=request.user)
    fund=get_object_or_404(ScholarshipFund,pk=pk,published=True)
    class ApplyForm(forms.Form):
        amount=forms.DecimalField(min_value=Decimal("0.01"),max_digits=12,decimal_places=2,label="Requested award")
        statement=forms.CharField(max_length=4000,widget=forms.Textarea,help_text="Explain how you meet the published criteria. Do not include medical evidence, card details or banking credentials.")
        renewal=forms.ModelChoiceField(queryset=ScholarshipAward.objects.filter(application__student=student,status="disbursed",fund__code=fund.code).select_related("fund"),required=False,label="Prior award for renewal")
    form=ApplyForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            item=submit_application(student,fund,data["amount"],data["statement"],data["renewal"])
            return redirect("scholarship_application",pk=item.pk)
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,"An application is already recorded. Review your scholarship history.")
    return render(request,"form.html",{"form":form,"heading":"Apply: "+fund.name,"notice":fund.description})


def accessible_application(user,pk):
    rows=ScholarshipApplication.objects.select_related("fund","student","award")
    if not staff_access(user): rows=rows.filter(student__user=user)
    return get_object_or_404(rows,pk=pk)


@login_required
def detail(request,pk):
    item=accessible_application(request.user,pk)
    response=render(request,"scholarship_application.html",{"item":item,"events":item.events.order_by("created"),"scholarship_staff":staff_access(request.user),"is_owner":item.student.user_id==request.user.pk})
    response["Cache-Control"]="private, no-store"
    return response


@login_required
def decide(request,pk):
    item=accessible_application(request.user,pk)
    staff=staff_access(request.user) and request.user.has_perms(["academics.change_scholarshipapplication","academics.add_scholarshipaward"])
    owner=item.student.user_id==request.user.pk
    if not staff and not owner: return HttpResponseForbidden()
    class DecisionForm(forms.Form):
        outcome=forms.ChoiceField(choices=[("approved","Approve"),("declined","Decline")] if staff else [("withdrawn","Withdraw my pending application")])
        amount=forms.DecimalField(required=False,min_value=Decimal("0.01"),max_digits=12,decimal_places=2,label="Approved amount (approval only)")
        reason=forms.CharField(max_length=2000,widget=forms.Textarea,help_text="This reason is visible to the applicant.")
    form=DecisionForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            decide_application(item,data["outcome"],data["reason"],request.user,data["amount"])
            return redirect("scholarship_application",pk=pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Scholarship decision"})


@login_required
@permission_required("academics.change_scholarshipaward",raise_exception=True)
def award_action(request,pk,action):
    if not staff_access(request.user): return HttpResponseForbidden()
    award=get_object_or_404(ScholarshipAward,pk=pk)
    if action not in {"post","cancel","reverse"}: return HttpResponseForbidden()
    class ActionForm(forms.Form):
        reason=forms.CharField(max_length=2000,widget=forms.Textarea,help_text="Record authorization and the reason visible to the student.")
        confirmed=forms.BooleanField(label="I confirm this authorized account adjustment")
    form=ActionForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            change_award(award,action,form.cleaned_data["reason"],request.user)
            return redirect("scholarship_application",pk=award.application_id)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":{"post":"Post scholarship credit","cancel":"Cancel unposted award","reverse":"Reverse posted scholarship credit"}[action],"notice":"This changes the student's institutional account only. It does not transfer money to a bank account."})
