from io import BytesIO
from datetime import timedelta
from zoneinfo import available_timezones
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db import transaction,IntegrityError
from django.http import HttpResponse,Http404,HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image,UnidentifiedImageError
from .institution import InstitutionSettings,PortalPreference,ImportBatch
from .bulk_imports import HEADERS,parse_csv,validate_rows,rows_digest
from .attachment_views import AttachmentForm
from .operations import AuditEvent


@login_required
@permission_required("academics.change_institutionsettings",raise_exception=True)
def institution_settings(request):
    instance=InstitutionSettings.objects.filter(pk=1).first() or InstitutionSettings(name=settings.FTBI_INSTITUTION_NAME,short_name=settings.FTBI_INSTITUTION_SHORT_NAME)
    Form=forms.modelform_factory(InstitutionSettings,fields=["name","short_name","accent","header"])
    form=Form(request.POST if request.method=="POST" else None,instance=instance)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            InstitutionSettings.objects.update_or_create(pk=1,defaults=form.cleaned_data)
            AuditEvent.objects.create(actor=request.user,action="institution_branding_updated",target="1")
        return redirect("institution_settings")
    return render(request,"institution_settings.html",{"form":form})


@login_required
@permission_required("academics.change_institutionsettings",raise_exception=True)
def upload_logo(request):
    form=AttachmentForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            if len(form.payload)>512*1024: raise ValueError()
            with Image.open(BytesIO(form.payload)) as source:
                if source.format not in {"PNG","JPEG"} or max(source.size)>2048: raise ValueError()
                source.load(); output=BytesIO(); source.convert("RGBA").save(output,format="PNG")
            if len(output.getvalue())>512*1024: raise ValueError()
        except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError): form.add_error("file","Upload a scanned PNG or JPEG no larger than 512 KB and 2048 pixels per side.")
        else:
            with transaction.atomic():
                instance=get_object_or_404(InstitutionSettings.objects.select_for_update(),pk=1)
                instance.logo=output.getvalue(); instance.logo_type="image/png"; instance.save(update_fields=["logo","logo_type","updated"])
                AuditEvent.objects.create(actor=request.user,action="institution_logo_uploaded",target="1")
            return redirect("institution_settings")
    return render(request,"institution_logo_upload.html",{"form":form})


def institution_logo(request):
    instance=get_object_or_404(InstitutionSettings,pk=1,logo_type="image/png")
    response=HttpResponse(bytes(instance.logo),content_type="image/png")
    response["Cache-Control"]="public, max-age=300"; response["X-Content-Type-Options"]="nosniff"
    return response


@login_required
def preferences(request):
    instance=PortalPreference.objects.filter(user=request.user).first() or PortalPreference(user=request.user,timezone=settings.TIME_ZONE)
    class PreferenceForm(forms.ModelForm):
        timezone=forms.ChoiceField(choices=[(name,name) for name in sorted(available_timezones())])
        class Meta:
            model=PortalPreference
            fields=["timezone","show_courses","show_services","course_order"]
    form=PreferenceForm(request.POST if request.method=="POST" else None,instance=instance)
    if request.method=="POST" and form.is_valid():
        PortalPreference.objects.update_or_create(user=request.user,defaults=form.cleaned_data)
        return redirect("preferences")
    return render(request,"form.html",{"form":form,"heading":"Portal preferences"})


def import_permission(user,kind):
    return user.has_perm("academics.add_studentprofile" if kind=="students" else "academics.add_course")

@login_required
def import_preview(request,kind):
    if kind not in HEADERS: raise Http404()
    if not import_permission(request.user,kind): return HttpResponseForbidden()
    class ImportForm(forms.Form): file=forms.FileField(help_text="UTF-8 CSV, up to 2 MB and 1000 rows. Existing records will not be overwritten.")
    form=ImportForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try: rows=parse_csv(kind,form.cleaned_data["file"].read(2*1024*1024+1))
        except ValidationError as error: form.add_error("file",error)
        else:
            batch=ImportBatch.objects.create(owner=request.user,kind=kind,rows=rows,digest=rows_digest(rows))
            AuditEvent.objects.create(actor=request.user,action="bulk_import_previewed",target=str(batch.pk))
            return redirect("import_detail",pk=batch.pk)
    return render(request,"import_upload.html",{"form":form,"kind":kind,"headers":", ".join(HEADERS[kind])})


@login_required
def import_detail(request,pk):
    batch=get_object_or_404(ImportBatch,pk=pk,owner=request.user)
    if not import_permission(request.user,batch.kind): return HttpResponseForbidden()
    return render(request,"import_detail.html",{"batch":batch,"headers":HEADERS[batch.kind],"rows":[[row[key] for key in HEADERS[batch.kind]] for row in batch.rows]})


@login_required
@require_POST
def import_commit(request,pk):
    try:
        with transaction.atomic():
            batch=get_object_or_404(ImportBatch.objects.select_for_update(),pk=pk,owner=request.user)
            if not import_permission(request.user,batch.kind): return HttpResponseForbidden()
            if batch.committed_at: return redirect("import_detail",pk=pk)
            if batch.created<timezone.now()-timedelta(hours=24): raise ValidationError("This preview expired. Upload a fresh file.")
            if rows_digest(batch.rows)!=batch.digest: raise ValidationError("Preview integrity check failed.")
            records=validate_rows(batch.kind,batch.rows)
            for record in records:
                if batch.kind=="students": record._status_actor=request.user
                record.save()
            batch.created_ids=[record.pk for record in records]; batch.committed_at=timezone.now(); batch.save(update_fields=["created_ids","committed_at"])
            AuditEvent.objects.create(actor=request.user,action="bulk_import_committed",target=str(pk))
    except (ValidationError,IntegrityError) as error:
        message="The records changed after preview. No rows were imported; upload a fresh file." if isinstance(error,IntegrityError) else "; ".join(error.messages)
        return render(request,"import_error.html",{"error":message},status=400)
    return redirect("import_detail",pk=pk)
