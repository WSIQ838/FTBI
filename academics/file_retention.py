"""Explicitly reviewed erasure of obsolete document-version payloads."""
import hashlib
import json
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator,MaxValueValidator
from django.db import models,transaction
from django.db.models import OuterRef,Subquery,Exists
from django.db.models.functions import Length
from django.utils import timezone
from .documents import PrivateDocument,DocumentVersion
from .operations import AuditEvent


class FileRetentionPolicy(models.Model):
    kind=models.CharField(max_length=16,unique=True,choices=[("institution","Institutional library"),("student","Student documents"),("admission","Application documents")])
    enabled=models.BooleanField(default=False)
    minimum_age_days=models.PositiveIntegerField(default=365,validators=[MinValueValidator(30),MaxValueValidator(36500)])
    keep_versions=models.PositiveSmallIntegerField(default=1,validators=[MinValueValidator(1),MaxValueValidator(20)])
    approval_reference=models.CharField(max_length=200,blank=True)
    def clean(self):
        if self.enabled and not self.approval_reference.strip(): raise ValidationError("Enabled retention requires institutional approval reference.")
    def __str__(self): return self.get_kind_display()


class DocumentPreservationHold(models.Model):
    document=models.ForeignKey(PrivateDocument,on_delete=models.PROTECT,related_name="preservation_holds")
    reason=models.TextField(max_length=2000)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="document_holds_created")
    created=models.DateTimeField(auto_now_add=True)
    released_at=models.DateTimeField(null=True)
    released_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,related_name="document_holds_released")
    release_reason=models.TextField(max_length=2000,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["document"],condition=models.Q(released_at__isnull=True),name="one_active_document_preservation_hold")]


class FileRetentionBatch(models.Model):
    policy=models.ForeignKey(FileRetentionPolicy,on_delete=models.PROTECT)
    policy_snapshot=models.JSONField()
    rows=models.JSONField()
    digest=models.CharField(max_length=64)
    reason=models.TextField(max_length=2000)
    proposed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="retention_batches_proposed")
    created=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,related_name="retention_batches_reviewed")


def snapshot(policy):
    return {"kind":policy.kind,"days":policy.minimum_age_days,"keep":policy.keep_versions,"approval":policy.approval_reference}


def digest(policy_snapshot,rows):
    return hashlib.sha256(json.dumps({"policy":policy_snapshot,"rows":rows},sort_keys=True,separators=(",",":")).encode()).hexdigest()


def eligible(policy):
    policy.full_clean()
    if not policy.enabled: raise ValidationError("Retention policy is disabled.")
    newest=DocumentVersion.objects.filter(document_id=OuterRef("document_id")).order_by("-number").values("pk")[:policy.keep_versions]
    holds=DocumentPreservationHold.objects.filter(document_id=OuterRef("document_id"),released_at__isnull=True)
    return DocumentVersion.objects.annotate(preserved=Exists(holds)).filter(preserved=False,document__kind=policy.kind,purged_at__isnull=True,uploaded__lt=timezone.now()-timedelta(days=policy.minimum_age_days),verification__isnull=True).exclude(pk__in=Subquery(newest)).order_by("pk")


def row_snapshot(row):
    return {"id":row.pk,"document":row.document_id,"number":row.number,"size":row.size,"sha256":row.sha256}


@transaction.atomic
def propose_batch(policy,actor,reason):
    if not actor.has_perm("academics.add_fileretentionbatch"): raise ValidationError("Retention proposal permission required.")
    if not reason.strip() or len(reason)>2000: raise ValidationError("Enter a reason of at most 2000 characters.")
    policy=FileRetentionPolicy.objects.select_for_update().get(pk=policy.pk)
    rows=[];total=0
    for row in eligible(policy).defer("data").annotate(actual_size=Length("data"))[:500]:
        if total+row.actual_size>50*1024*1024: break
        total+=row.actual_size;rows.append(row_snapshot(row))
    if not rows: raise ValidationError("No eligible obsolete versions.")
    data=snapshot(policy)
    batch=FileRetentionBatch.objects.create(policy=policy,policy_snapshot=data,rows=rows,digest=digest(data,rows),reason=reason,proposed_by=actor)
    AuditEvent.objects.create(actor=actor,action="file_retention_proposed",target=str(batch.pk))
    return batch


@transaction.atomic
def apply_batch(batch,actor):
    if not actor.has_perm("academics.change_fileretentionbatch"): raise ValidationError("Retention review permission required.")
    policy=FileRetentionPolicy.objects.select_for_update().get(pk=batch.policy_id)
    batch=FileRetentionBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.completed_at: raise ValidationError("This batch was already applied.")
    if batch.proposed_by_id==actor.pk: raise ValidationError("Another authorized reviewer must approve erasure.")
    if timezone.now()>=batch.created+timedelta(hours=24): raise ValidationError("Preview expired; create a fresh proposal.")
    if snapshot(policy)!=batch.policy_snapshot or digest(batch.policy_snapshot,batch.rows)!=batch.digest: raise ValidationError("Preview or policy changed; create a fresh proposal.")
    ids=[row["id"] for row in batch.rows]
    document_ids=sorted({row["document"] for row in batch.rows})
    list(PrivateDocument.objects.select_for_update(no_key=True).filter(pk__in=document_ids).order_by("pk"))
    rows=list(DocumentVersion.objects.select_for_update().filter(pk__in=ids).defer("data").annotate(actual_size=Length("data")).order_by("pk"))
    if len(rows)>500 or sum(row.actual_size for row in rows)>50*1024*1024: raise ValidationError("Batch exceeds the reviewed size limit.")
    allowed=set(eligible(policy).filter(pk__in=ids).values_list("pk",flat=True))
    if len(rows)!=len(ids) or allowed!=set(ids) or [row_snapshot(row) for row in rows]!=batch.rows: raise ValidationError("Eligibility changed; nothing erased. Create a fresh proposal.")
    for row in rows:
        if len(row.data)!=row.size or hashlib.sha256(bytes(row.data)).hexdigest()!=row.sha256: raise ValidationError("Stored file integrity failed; nothing erased.")
    now=timezone.now()
    DocumentVersion.objects.filter(pk__in=ids).update(data=b"",purged_at=now)
    batch.completed_at=now;batch.reviewed_by=actor;batch.save(update_fields=["completed_at","reviewed_by"])
    AuditEvent.objects.create(actor=actor,action="file_retention_applied",target=str(batch.pk))
    return len(rows)
