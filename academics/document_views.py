import hashlib
from pathlib import PurePath
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.http import Http404,HttpResponse,HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.utils.http import content_disposition_header
from .attachment_views import AttachmentForm
from .documents import PrivateDocument,DocumentVersion,DocumentVerification,StorageQuota,document_access,storage_used
from .models import Submission,Assignment,Enrollment
from .registrar import StudentProfile,Application
from .assessment_policy import submission_open
from .operations import AuditEvent


@login_required
def document_library(request):
    personal=PrivateDocument.objects.filter(owner=request.user).order_by("-created")
    library=PrivateDocument.objects.filter(kind="institution",published=True).order_by("title")
    return render(request,"documents.html",{"personal":personal,"library":library,"used":storage_used(request.user),"limit":getattr(StorageQuota.objects.filter(user=request.user).first(),"limit_bytes",104857600)})


@login_required
def upload_document(request,kind,pk=0):
    existing=get_object_or_404(PrivateDocument,pk=pk) if kind=="version" else None
    if existing:
        kind=existing.kind
        if existing.owner_id!=request.user.pk: raise Http404()
    application=None; submission=None
    if kind=="student": get_object_or_404(StudentProfile,user=request.user)
    elif kind=="admission": application=get_object_or_404(Application,pk=existing.application_id if existing else pk,applicant=request.user,status="pending")
    elif kind=="institution":
        if not request.user.has_perms(["academics.add_privatedocument","academics.change_libraryresource"]): return HttpResponseForbidden()
    elif kind=="coursework":
        submission=get_object_or_404(Submission,pk=existing.submission_id if existing else pk,student=request.user,assignment__course__published=True)
        if not Enrollment.objects.filter(student=request.user,course=submission.assignment.course,active=True).exists(): raise Http404()
    else: raise Http404()
    class UploadForm(AttachmentForm):
        title=forms.CharField(max_length=200)
    form=UploadForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None,initial={"title":existing.title if existing else ""})
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            if application:
                application=Application.objects.select_for_update().get(pk=application.pk)
                if application.status!="pending": return HttpResponseForbidden("Application is closed.")
            if submission:
                Assignment.objects.select_for_update().get(pk=submission.assignment_id)
                submission.refresh_from_db()
                if not submission_open(submission.assignment,submission,attachment=True): return HttpResponseForbidden("Submission is closed.")
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            quota=getattr(StorageQuota.objects.filter(user=request.user).first(),"limit_bytes",104857600)
            if storage_used(request.user)+len(form.payload)>quota:
                form.add_error("file","Storage quota exceeded. Contact records support.")
            else:
                document=existing or PrivateDocument.objects.create(owner=request.user,title=form.cleaned_data["title"],kind=kind,application=application,submission=submission)
                number=document.versions.count()+1
                version=DocumentVersion.objects.create(document=document,number=number,original_name=PurePath(form.cleaned_data["file"].name).name[:200],data=form.payload,size=len(form.payload),sha256=hashlib.sha256(form.payload).hexdigest(),uploaded_by=request.user)
                AuditEvent.objects.create(actor=request.user,action="document_version_uploaded",target=str(version.pk))
                return redirect("document_detail",pk=document.pk)
    return render(request,"document_upload.html",{"form":form})


@login_required
def document_detail(request,pk):
    document=get_object_or_404(PrivateDocument,pk=pk)
    if not document_access(request.user,document): raise Http404()
    return render(request,"document_detail.html",{"document":document,"versions":document.versions.select_related("verification").all()})


@login_required
def document_download(request,pk):
    version=get_object_or_404(DocumentVersion.objects.select_related("document"),pk=pk)
    if not document_access(request.user,version.document): raise Http404()
    AuditEvent.objects.create(actor=request.user,action="private_document_downloaded",target=str(pk))
    response=HttpResponse(bytes(version.data),content_type="application/octet-stream")
    response["Content-Disposition"]=content_disposition_header(True,version.original_name)
    response["Cache-Control"]="private, no-store"; response["X-Content-Type-Options"]="nosniff"
    return response


@login_required
@permission_required("academics.add_documentverification",raise_exception=True)
def verify_document(request,pk):
    version=get_object_or_404(DocumentVersion.objects.select_related("document"),pk=pk)
    if version.document.owner_id==request.user.pk or not document_access(request.user,version.document) or version.document.kind not in {"admission","student"}: raise Http404()
    class VerifyForm(forms.Form):
        status=forms.ChoiceField(choices=DocumentVerification._meta.get_field("status").choices)
        note=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=VerifyForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            DocumentVersion.objects.select_for_update().get(pk=pk)
            if DocumentVerification.objects.filter(version=version).exists(): return HttpResponseForbidden("This version has already been reviewed.")
            DocumentVerification.objects.create(version=version,reviewer=request.user,**form.cleaned_data)
            AuditEvent.objects.create(actor=request.user,action="document_"+form.cleaned_data["status"],target=str(pk))
        return redirect("document_detail",pk=version.document_id)
    return render(request,"form.html",{"form":form,"heading":"Verify document version"})
