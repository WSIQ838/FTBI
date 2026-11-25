import hashlib
import secrets
from io import BytesIO
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import Http404,HttpResponse,FileResponse,HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from .credentials import CredentialArtifact,CredentialRevocation,CredentialReplacement
from .credential_service import seal_record,CredentialSigningError
from .transcripts import IssuedTranscript
from .diplomas import IssuedDiploma
from .operations import AuditEvent

def manage_credential(user,kind):
    return user.has_perms(["academics.change_credentialartifact","academics.view_studentprofile","academics.view_finalgrade",f"academics.add_issued{kind}"])

def scoped_credentials(user):
    rows=CredentialArtifact.objects.defer("pdf")
    if user.has_perms(["academics.view_credentialartifact","academics.view_studentprofile"]): return rows
    return rows.filter(student__user=user)

def serve_credential(request,artifact):
    if CredentialRevocation.objects.filter(credential=artifact).exists(): return HttpResponseForbidden("This credential has been revoked. Contact the registrar.")
    AuditEvent.objects.create(actor=request.user,action="credential_pdf_downloaded",target=str(artifact.identifier))
    response=FileResponse(BytesIO(bytes(artifact.pdf)),as_attachment=True,filename=artifact.kind+".pdf",content_type="application/pdf")
    response["Cache-Control"]="private, no-store"
    return response

@login_required
def credential_list(request):
    rows=scoped_credentials(request.user).select_related("revocation","replacement").order_by("-issued_at")[:200]
    response=render(request,"credentials.html",{"rows":rows})
    response["Cache-Control"]="private, no-store"
    return response

@login_required
def credential_pdf(request,identifier):
    artifact=get_object_or_404(scoped_credentials(request.user),identifier=identifier)
    return serve_credential(request,artifact)

@login_required
def revoke_credential(request,identifier):
    artifact=get_object_or_404(CredentialArtifact,identifier=identifier)
    if not manage_credential(request.user,artifact.kind): return HttpResponseForbidden()
    class ReasonForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReasonForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            artifact=CredentialArtifact.objects.select_for_update().get(pk=artifact.pk)
            revocation,created=CredentialRevocation.objects.get_or_create(credential=artifact,defaults={"reason":form.cleaned_data["reason"],"revoked_by":request.user})
            if created: AuditEvent.objects.create(actor=request.user,action="credential_revoked",target=str(identifier))
        return redirect("credential_list")
    return render(request,"form.html",{"form":form,"heading":"Revoke credential"})

@login_required
def reissue_credential(request,identifier):
    artifact=get_object_or_404(CredentialArtifact,identifier=identifier)
    if not manage_credential(request.user,artifact.kind): return HttpResponseForbidden()
    class ReasonForm(forms.Form): reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    form=ReasonForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            with transaction.atomic():
                artifact=CredentialArtifact.objects.select_for_update().get(pk=artifact.pk)
                if not CredentialRevocation.objects.filter(credential=artifact).exists(): return HttpResponseForbidden("Revoke the original credential before issuing its replacement.")
                existing=CredentialReplacement.objects.filter(original=artifact).first()
                if not existing: seal_record(artifact.kind,artifact.transcript or artifact.diploma,request.user,original=artifact,reason=form.cleaned_data["reason"])
        except CredentialSigningError: return HttpResponse("Credential signing is unavailable. No replacement was issued.",status=503)
        return redirect("credential_list")
    return render(request,"form.html",{"form":form,"heading":"Reissue original academic snapshot with a new identifier"})

@login_required
def finalize_legacy(request):
    class FinalizeForm(forms.Form):
        kind=forms.ChoiceField(choices=[("transcript","Transcript"),("diploma","Diploma")])
        identifier=forms.UUIDField()
    if not request.user.has_perm("academics.change_credentialartifact"): return HttpResponseForbidden()
    form=FinalizeForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        kind=form.cleaned_data["kind"]
        if not manage_credential(request.user,kind): return HttpResponseForbidden()
        record=get_object_or_404(IssuedTranscript if kind=="transcript" else IssuedDiploma,identifier=form.cleaned_data["identifier"])
        try: seal_record(kind,record,request.user)
        except CredentialSigningError: return HttpResponse("Credential signing is unavailable. No credential was finalized.",status=503)
        return redirect("credential_list")
    return render(request,"form.html",{"form":form,"heading":"Finalize an existing issued record"})

def verify_credential(request):
    class VerifyForm(forms.Form):
        identifier=forms.UUIDField(label="Credential ID")
        code=forms.CharField(max_length=40,label="Verification code")
        pdf=forms.FileField(required=False,label="Credential PDF (optional)",help_text="Up to 10 MB. Used only to compare the file digest; it is not stored.")
    form=VerifyForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None)
    result=None
    if request.method=="POST":
        key="credential-verification:"+hashlib.sha256(request.META.get("REMOTE_ADDR","unknown").encode()).hexdigest()
        cache.add(key,0,3600)
        try: count=cache.incr(key)
        except ValueError: count=31
        if count>30: return HttpResponse("Too many verification requests. Try later.",status=429)
        if form.is_valid():
            artifact=CredentialArtifact.objects.defer("pdf").filter(identifier=form.cleaned_data["identifier"]).first()
            if not artifact or not secrets.compare_digest(artifact.verification_code,form.cleaned_data["code"]): form.add_error(None,"Credential details could not be verified.")
            else:
                match=None
                if form.cleaned_data["pdf"]:
                    data=form.cleaned_data["pdf"].read(10*1024*1024+1)
                    if len(data)>10*1024*1024: form.add_error("pdf","PDF must be no larger than 10 MB.")
                    else: match=secrets.compare_digest(hashlib.sha256(data).hexdigest(),artifact.sha256)
                if not form.errors:
                    result={"kind":artifact.kind,"institution":artifact.snapshot["institution"],"issued":artifact.issued_at,"revoked":CredentialRevocation.objects.filter(credential=artifact).exists(),"signed":artifact.signed,"file_checked":match is not None,"file_matches":match,"fingerprint":artifact.certificate_fingerprint}
    response=render(request,"credential_verification.html",{"form":form,"result":result})
    response["Cache-Control"]="no-store";response["Referrer-Policy"]="no-referrer"
    return response
