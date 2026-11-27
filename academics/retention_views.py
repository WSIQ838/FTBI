from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from .file_retention import FileRetentionPolicy,FileRetentionBatch,DocumentPreservationHold,propose_batch,apply_batch
from .documents import PrivateDocument
from .operations import AuditEvent


@login_required
@permission_required("academics.view_fileretentionbatch",raise_exception=True)
def retention_home(request):
    class ProposalForm(forms.Form):
        policy=forms.ModelChoiceField(queryset=FileRetentionPolicy.objects.filter(enabled=True))
        reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ProposalForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try: batch=propose_batch(form.cleaned_data["policy"],request.user,form.cleaned_data["reason"])
        except ValidationError as exc: form.add_error(None,exc)
        else: return redirect("retention_batch",pk=batch.pk)
    return render(request,"retention.html",{"form":form,"batches":FileRetentionBatch.objects.order_by("-created")[:100],"holds":DocumentPreservationHold.objects.filter(released_at__isnull=True).order_by("created")[:100]})


@login_required
@permission_required("academics.view_fileretentionbatch",raise_exception=True)
def review_batch(request,pk):
    batch=get_object_or_404(FileRetentionBatch,pk=pk)
    class ApprovalForm(forms.Form):
        confirm=forms.BooleanField(label="I independently reviewed this preview and approve permanent removal of these file contents from the active database.")
    form=ApprovalForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try: apply_batch(batch,request.user)
        except ValidationError as exc: form.add_error(None,exc)
        else: return redirect("retention_batch",pk=pk)
    return render(request,"retention_batch.html",{"batch":batch,"form":form,"total_bytes":sum(row["size"] for row in batch.rows)})


@login_required
@permission_required("academics.add_documentpreservationhold",raise_exception=True)
def add_hold(request):
    class HoldForm(forms.Form):
        document_id=forms.IntegerField(min_value=1)
        reason=forms.CharField(max_length=2000,widget=forms.Textarea,help_text="Use an approved case/reference; do not enter medical evidence.")
    form=HoldForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            document=get_object_or_404(PrivateDocument.objects.select_for_update(no_key=True),pk=form.cleaned_data["document_id"])
            hold,created=DocumentPreservationHold.objects.get_or_create(document=document,released_at__isnull=True,defaults={"reason":form.cleaned_data["reason"],"created_by":request.user})
            if created: AuditEvent.objects.create(actor=request.user,action="document_preservation_hold_added",target=str(hold.pk))
        return redirect("file_retention")
    return render(request,"form.html",{"form":form,"heading":"Preserve document versions"})


@login_required
@permission_required("academics.change_documentpreservationhold",raise_exception=True)
def release_hold(request,pk):
    hold=get_object_or_404(DocumentPreservationHold,pk=pk)
    class ReleaseForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReleaseForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            PrivateDocument.objects.select_for_update(no_key=True).get(pk=hold.document_id)
            hold=DocumentPreservationHold.objects.select_for_update().get(pk=pk)
            if hold.released_at: return HttpResponseForbidden("This hold has already been released.")
            hold.released_at=timezone.now();hold.released_by=request.user;hold.release_reason=form.cleaned_data["reason"];hold.save()
            AuditEvent.objects.create(actor=request.user,action="document_preservation_hold_released",target=str(pk))
        return redirect("file_retention")
    return render(request,"form.html",{"form":form,"heading":"Release preservation hold","notice":"Releasing the hold permits future reviewed retention; it does not erase any files now."})
