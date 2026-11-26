"""Bounded aggregate reports with current role scope and reviewed snapshots."""
import hashlib
import json
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import models,transaction
from django.db.models import Count,Sum
from django.utils import timezone
from .models import Department,Program,Term,Enrollment
from .registrar import StudentProfile,Application
from .services import FinalGrade
from .operations import AuditEvent


class Campus(models.Model):
    code=models.CharField(max_length=20,unique=True)
    name=models.CharField(max_length=150)
    active=models.BooleanField(default=True)
    address=models.TextField(max_length=1000,blank=True)
    def __str__(self): return f"{self.code}: {self.name}"


class DeanAssignment(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["user","department"],name="unique_dean_department")]


DATASETS={
    "students":{"model":StudentProfile,"permission":"view_studentprofile","department":"program__department_id","campus":"campus_id","groups":{"department":("program__department_id","program__department__name"),"program":("program_id","program__name"),"campus":("campus_id","campus__name"),"status":("status",)},"statuses":["active","leave","graduated","withdrawn"]},
    "admissions":{"model":Application,"permission":"view_application","department":"program__department_id","campus":"campus_id","groups":{"department":("program__department_id","program__department__name"),"program":("program_id","program__name"),"campus":("campus_id","campus__name"),"status":("status",)},"statuses":["pending","accepted","rejected"]},
    "enrollments":{"model":Enrollment,"permission":"view_enrollment","department":"course__department_id","campus":"course__campus_id","term":"course__term_id","groups":{"department":("course__department_id","course__department__name"),"campus":("course__campus_id","course__campus__name"),"term":("course__term_id","course__term__name"),"status":("active",)},"statuses":["active","inactive"]},
    "grades":{"model":FinalGrade,"permission":"view_finalgrade","department":"course__department_id","campus":"course__campus_id","term":"course__term_id","groups":{"department":("course__department_id","course__department__name"),"campus":("course__campus_id","course__campus__name"),"term":("course__term_id","course__term__name"),"status":("letter",)},"statuses":[]},
}


class InstitutionalReport(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    title=models.CharField(max_length=150)
    dataset=models.CharField(max_length=20,choices=[(x,x.title()) for x in DATASETS])
    group_by=models.CharField(max_length=20,choices=[(x,x.title()) for x in ["department","program","campus","term","status"]])
    department=models.ForeignKey(Department,on_delete=models.PROTECT,null=True,blank=True)
    campus=models.ForeignKey(Campus,on_delete=models.PROTECT,null=True,blank=True)
    term=models.ForeignKey(Term,on_delete=models.PROTECT,null=True,blank=True)
    status_filter=models.CharField(max_length=20,blank=True)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        permissions=[("view_president_dashboard","View institution-wide leadership aggregates"),("view_dean_dashboard","View assigned department aggregates"),("review_report_snapshot","Review institutional report snapshots")]
    def clean(self):
        spec=DATASETS.get(self.dataset)
        if not spec or self.group_by not in spec["groups"]: raise ValidationError("Choose a grouping supported by this dataset.")
        if self.term_id and "term" not in spec: raise ValidationError("Term filtering is available for enrollments and released grades.")
        if self.status_filter and self.status_filter not in spec["statuses"]: raise ValidationError("Unsupported status filter.")


class ReportSnapshot(models.Model):
    report=models.ForeignKey(InstitutionalReport,on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    purpose=models.CharField(max_length=500)
    evidence_reference=models.CharField(max_length=500)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if self.pk: raise ValueError("Report snapshots are immutable.")
        super().save(*args,**kwargs)


class ReportReview(models.Model):
    snapshot=models.OneToOneField(ReportSnapshot,on_delete=models.PROTECT,related_name="review")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    approved=models.BooleanField()
    reason=models.TextField(max_length=2000)
    created=models.DateTimeField(auto_now_add=True)


def is_president(user): return user.is_staff and user.has_perm("academics.view_president_dashboard")


def report_scope(user,dataset):
    if dataset not in DATASETS or not user.is_staff: raise PermissionDenied()
    if is_president(user): return None
    # A dean's department scope takes precedence over separately granted model permissions.
    if user.has_perm("academics.view_dean_dashboard"):
        ids=list(DeanAssignment.objects.filter(user=user,active=True).values_list("department_id",flat=True))
        if not ids: raise PermissionDenied("No active department assignment.")
        return sorted(ids)
    if user.has_perms(["academics.view_institutionalreport","academics."+DATASETS[dataset]["permission"]]): return None
    raise PermissionDenied()


def execute_report(user,report):
    report.full_clean(exclude=["owner"])
    scope=report_scope(user,report.dataset)
    if scope is not None and report.department_id and report.department_id not in scope: raise PermissionDenied()
    spec=DATASETS[report.dataset];rows=spec["model"].objects.all()
    if scope is not None: rows=rows.filter(**{spec["department"]+"__in":scope})
    if report.department_id: rows=rows.filter(**{spec["department"]:report.department_id})
    if report.campus_id: rows=rows.filter(**{spec["campus"]:report.campus_id})
    if report.term_id: rows=rows.filter(**{spec["term"]:report.term_id})
    if report.status_filter:
        rows=rows.filter(active=report.status_filter=="active") if report.dataset=="enrollments" else rows.filter(status=report.status_filter)
    if report.dataset=="grades": rows=rows.filter(released=True)
    fields=spec["groups"][report.group_by]
    metrics={"count":Count("pk")}
    if report.dataset=="enrollments": metrics["unique_students"]=Count("student_id",distinct=True)
    if report.dataset=="grades": metrics["earned_credits"]=Sum("credits_earned")
    aggregate=list(rows.values(*fields).annotate(**metrics).order_by(*fields)[:501])
    if len(aggregate)>500: raise ValidationError("This report exceeds 500 groups. Narrow its filters.")
    result=[]
    for entry in aggregate:
        label=entry[fields[-1]]
        if report.dataset=="enrollments" and report.group_by=="status": label="Active" if label else "Inactive"
        result.append({"key":str(entry[fields[0]]) if entry[fields[0]] is not None else "unassigned","label":str(label) if label is not None else "Unassigned","count":entry["count"],**{key:entry[key] or 0 for key in metrics if key!="count"}})
    return {"version":1,"title":report.title,"dataset":report.dataset,"group_by":report.group_by,"department_id":report.department_id,"campus_id":report.campus_id,"term_id":report.term_id,"status_filter":report.status_filter,"department_scope":scope,"generated_at":timezone.now().isoformat(),"rows":result,"metrics":list(metrics)}


def digest(payload): return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def snapshot_access(user,snapshot):
    scope=report_scope(user,snapshot.payload["dataset"])
    old_scope=snapshot.payload["department_scope"]
    if scope is not None and (old_scope is None or not set(old_scope).issubset(scope)): raise PermissionDenied("Snapshot scope exceeds your current assignment.")
    if snapshot.created_by_id!=user.pk and not user.has_perm("academics.review_report_snapshot"): raise PermissionDenied()
    if digest(snapshot.payload)!=snapshot.sha256: raise ValidationError("Snapshot integrity check failed.")


@transaction.atomic
def capture_report(user,report,purpose,evidence_reference):
    report=InstitutionalReport.objects.select_for_update().get(pk=report.pk,owner=user)
    payload=execute_report(user,report)
    item=ReportSnapshot(report=report,created_by=user,purpose=purpose,evidence_reference=evidence_reference,payload=payload,sha256=digest(payload))
    item.full_clean();item.save()
    AuditEvent.objects.create(actor=user,action="report_snapshot_created",target=str(item.pk))
    return item


@transaction.atomic
def review_snapshot(user,snapshot,approved,reason):
    snapshot=ReportSnapshot.objects.select_for_update().get(pk=snapshot.pk)
    snapshot_access(user,snapshot)
    if not user.has_perm("academics.review_report_snapshot") or snapshot.created_by_id==user.pk: raise PermissionDenied("A different authorized reviewer is required.")
    if not reason.strip(): raise ValidationError("Review reason is required.")
    prior=ReportReview.objects.filter(snapshot=snapshot).first()
    if prior:
        if prior.approved!=approved: raise ValidationError("This snapshot already has a different review decision.")
        return prior
    review=ReportReview(snapshot=snapshot,reviewer=user,approved=approved,reason=reason)
    review.full_clean();review.save()
    AuditEvent.objects.create(actor=user,action="report_snapshot_approved" if approved else "report_snapshot_rejected",target=str(snapshot.pk))
    return review
