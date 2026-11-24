import csv
from django.contrib.auth.decorators import login_required,permission_required
from django.db.models import Count,Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from .models import Course,Enrollment,Submission,Program
from .registrar import StudentProfile,Application
from .services import LedgerEntry,LearningOutcome
from .degree import GraduationApplication
from .operations import TranscriptRequest,FinancialAidAward,AuditEvent
from .payments import PaymentRequest

@login_required
def workspaces(request):
    u=request.user
    panels=[]
    def permitted(*names):
        return u.has_perms(["academics.view_"+name for name in names])
    def add(title,metrics,links):
        panels.append({"title":title,"metrics":metrics,"links":links})
    teaching=Course.objects.filter(instructor=u)
    if teaching.exists():
        add("Faculty",[("Assigned sections",teaching.count()),("Active enrollments",Enrollment.objects.filter(course__in=teaching,active=True).count()),("Awaiting grading",Submission.objects.filter(assignment__course__in=teaching,grade__isnull=True).count())],[("My courses","dashboard")])
    if permitted("studentprofile","enrollment","transcriptrequest","graduationapplication"):
        add("Registrar",[("Active students",StudentProfile.objects.filter(status="active").count()),("Active enrollments",Enrollment.objects.filter(active=True).count()),("Pending transcripts",TranscriptRequest.objects.filter(status="pending").count()),("Pending graduation applications",GraduationApplication.objects.filter(status="pending").count())],[("Academic administration","admin:index") ] if u.is_staff else [])
    if permitted("application"):
        add("Admissions",[("Pending applications",Application.objects.filter(status="pending").count()),("Accepted applications",Application.objects.filter(status="accepted").count()),("Rejected applications",Application.objects.filter(status="rejected").count())],[("Applications","admin:academics_application_changelist")] if u.is_staff else [])
    if permitted("ledgerentry","paymentrequest","financialaidaward"):
        add("Finance",[("Net released ledger balance (USD)",LedgerEntry.objects.filter(released=True).aggregate(total=Sum("amount"))["total"] or 0),("Pending payments",PaymentRequest.objects.filter(status="pending").count()),("Pending aid awards",FinancialAidAward.objects.filter(status="pending").count())],[("Payment requests","admin:academics_paymentrequest_changelist")] if u.is_staff else [])
    if permitted("course","learningoutcome"):
        add("Academic affairs",[("Published sections",Course.objects.filter(published=True).count()),("Learning outcomes",LearningOutcome.objects.count()),("Unassessed outcomes",LearningOutcome.objects.filter(assessed_on__isnull=True).count())],[("Learning outcomes","admin:academics_learningoutcome_changelist")] if u.is_staff else [])
    if permitted("studentprofile","enrollment","application"):
        add("Institutional leadership",[("Students",StudentProfile.objects.count()),("Active enrollments",Enrollment.objects.filter(active=True).count()),("Applications",Application.objects.count())],[("Institutional reports","reports"),("Download aggregate CSV","institutional_csv")])
    if permitted("auditevent"):
        add("IT and security",[("Audit events today",AuditEvent.objects.filter(created__date=timezone.localdate()).count()),("Total audit events",AuditEvent.objects.count())],[("Audit log","admin:academics_auditevent_changelist")] if u.is_staff else [])
    return render(request,"workspaces.html",{"panels":panels})

@login_required
@permission_required("academics.view_studentprofile",raise_exception=True)
@permission_required("academics.view_enrollment",raise_exception=True)
@permission_required("academics.view_application",raise_exception=True)
def institutional_csv(request):
    response=HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"]='attachment; filename="institutional-summary.csv"'
    response["Cache-Control"]="private, no-store"
    writer=csv.writer(response)
    writer.writerow(["Metric","Count"])
    writer.writerow(["Students",StudentProfile.objects.count()])
    writer.writerow(["Active enrollments",Enrollment.objects.filter(active=True).count()])
    for entry in Application.objects.values("status").annotate(total=Count("id")).order_by("status"):
        writer.writerow(["Applications: "+entry["status"],entry["total"]])
    return response
