import csv
from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from .models import Department
from .institutional_reporting import InstitutionalReport,ReportSnapshot,ReportReview,DATASETS,execute_report,report_scope,is_president,capture_report,snapshot_access,review_snapshot
from .operations import AuditEvent


def private(response):
    response["Cache-Control"]="private, no-store"
    return response


def csv_response(payload,filename):
    response=private(HttpResponse(content_type="text/csv; charset=utf-8"))
    response["Content-Disposition"]='attachment; filename="'+filename+'"'
    writer=csv.writer(response)
    writer.writerow(["group_key","group"]+payload["metrics"])
    for row in payload["rows"]:
        label=row["label"]
        if label.lstrip().startswith(("=","+","-","@")): label="'"+label
        key=row["key"]
        if key.lstrip().startswith(("=","+","-","@")): key="'"+key
        writer.writerow([key,label]+[row[key] for key in payload["metrics"]])
    return response


@login_required
@permission_required("academics.view_institutionalreport",raise_exception=True)
def builder(request):
    if not request.user.is_staff: raise PermissionDenied()
    return private(render(request,"report_builder.html",{"reports":InstitutionalReport.objects.filter(owner=request.user).order_by("-created")}))


@login_required
@permission_required("academics.add_institutionalreport",raise_exception=True)
def create_report(request):
    if not request.user.is_staff: raise PermissionDenied()
    class ReportForm(forms.ModelForm):
        class Meta:
            model=InstitutionalReport
            fields=["title","dataset","group_by","department","campus","term","status_filter"]
        def clean(self):
            values=super().clean()
            if values.get("dataset"):
                try:
                    scope=report_scope(request.user,values["dataset"])
                    if scope is not None and values.get("department") and values["department"].pk not in scope: raise forms.ValidationError("Department is outside your current scope.")
                except PermissionDenied: raise forms.ValidationError("You do not have access to this dataset.")
            return values
    form=ReportForm(request.POST if request.method=="POST" else None)
    if request.user.has_perm("academics.view_dean_dashboard") and not is_president(request.user):
        from .institutional_reporting import DeanAssignment
        form.fields["department"].queryset=Department.objects.filter(deanassignment__user=request.user,deanassignment__active=True)
    if request.method=="POST" and form.is_valid():
        report=form.save(commit=False);report.owner=request.user;report.save()
        AuditEvent.objects.create(actor=request.user,action="report_definition_created",target=str(report.pk))
        return redirect("run_institutional_report",pk=report.pk)
    return render(request,"form.html",{"form":form,"heading":"Create aggregate report","notice":"Choose a supported dataset and grouping. Program grouping applies to students/admissions; term filters apply to enrollments/grades. Status filters use the documented dataset values. No individual student rows are exported."})


@login_required
@permission_required("academics.view_institutionalreport",raise_exception=True)
def run_report(request,pk):
    report=get_object_or_404(InstitutionalReport,pk=pk,owner=request.user)
    try: payload=execute_report(request.user,report)
    except ValidationError as error: return HttpResponse("; ".join(error.messages),status=400)
    if request.GET.get("format")=="csv":
        AuditEvent.objects.create(actor=request.user,action="aggregate_report_exported",target=str(report.pk))
        return csv_response(payload,"aggregate-report.csv")
    return private(render(request,"aggregate_report.html",{"report":report,"payload":payload,"snapshots":ReportSnapshot.objects.filter(report=report).order_by("-created")}))


@login_required
@permission_required("academics.add_reportsnapshot",raise_exception=True)
def capture(request,pk):
    report=get_object_or_404(InstitutionalReport,pk=pk,owner=request.user)
    class CaptureForm(forms.Form):
        purpose=forms.CharField(max_length=500,label="Reporting purpose / accreditation criterion")
        evidence_reference=forms.CharField(max_length=500,label="Institutional evidence reference",help_text="Use a document or review reference; do not paste private access tokens or personal records.")
    form=CaptureForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            item=capture_report(request.user,report,form.cleaned_data["purpose"],form.cleaned_data["evidence_reference"])
            return redirect("report_snapshot",pk=item.pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Capture report for independent review"})


@login_required
@permission_required("academics.view_reportsnapshot",raise_exception=True)
def snapshot_detail(request,pk):
    snapshot=get_object_or_404(ReportSnapshot,pk=pk)
    try: snapshot_access(request.user,snapshot)
    except ValidationError: return HttpResponse("Snapshot integrity check failed.",status=409)
    review=ReportReview.objects.filter(snapshot=snapshot).first()
    if request.GET.get("format")=="csv":
        if not review or not review.approved: raise PermissionDenied("Approve the snapshot before exporting it for institutional reporting.")
        AuditEvent.objects.create(actor=request.user,action="report_snapshot_exported",target=str(pk))
        return csv_response(snapshot.payload,"approved-report-snapshot.csv")
    return private(render(request,"aggregate_report.html",{"snapshot":snapshot,"payload":snapshot.payload,"review":review}))


@login_required
@permission_required("academics.review_report_snapshot",raise_exception=True)
def review(request,pk):
    snapshot=get_object_or_404(ReportSnapshot,pk=pk)
    try: snapshot_access(request.user,snapshot)
    except ValidationError: return HttpResponse("Snapshot integrity check failed.",status=409)
    class ReviewForm(forms.Form):
        decision=forms.ChoiceField(choices=[("approved","Approve"),("rejected","Reject")])
        reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReviewForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            review_snapshot(request.user,snapshot,form.cleaned_data["decision"]=="approved",form.cleaned_data["reason"])
            return redirect("report_snapshot",pk=pk)
        except ValidationError as error: form.add_error(None,error)
    return render(request,"form.html",{"form":form,"heading":"Review fixed report snapshot"})


@login_required
@permission_required("academics.review_report_snapshot",raise_exception=True)
def review_queue(request):
    rows=[]
    for snapshot in ReportSnapshot.objects.filter(review__isnull=True).exclude(created_by=request.user).order_by("created")[:200]:
        try: snapshot_access(request.user,snapshot)
        except (PermissionDenied,ValidationError): continue
        rows.append(snapshot)
    return private(render(request,"report_review_queue.html",{"snapshots":rows}))


@login_required
def leadership(request,role):
    if role=="president":
        if not is_president(request.user): raise PermissionDenied()
    elif role=="dean":
        if not request.user.is_staff or not request.user.has_perm("academics.view_dean_dashboard"): raise PermissionDenied()
    else: raise PermissionDenied()
    panels=[]
    for dataset,group,status in [("students","program","active"),("admissions","status",""),("enrollments","term","active"),("grades","term","")]:
        report=InstitutionalReport(owner=request.user,title=dataset.title(),dataset=dataset,group_by=group,status_filter=status)
        panels.append(execute_report(request.user,report))
    return private(render(request,"leadership_dashboard.html",{"role":role.title(),"panels":panels}))
