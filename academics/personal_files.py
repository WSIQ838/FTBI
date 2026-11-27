"""Bounded private archives of files already downloadable by their owner."""
import hashlib
import json
import tempfile
import zipfile
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models.functions import Length
from django.http import FileResponse,HttpResponse,HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_POST
from .documents import DocumentVersion,document_access
from .attachments import SubmissionAttachment
from .assessment_policy import SubmissionRevision
from .credentials import CredentialArtifact
from .operations import AuditEvent
from .views import visible_courses

MAX_FILES=500
MAX_BYTES=50*1024*1024


def build_archive(user):
    courses=visible_courses(user)
    specs=[
        ("document",DocumentVersion.objects.filter(document__owner=user).select_related("document","document__submission__assignment__course"),"data","original_name"),
        ("attachment",SubmissionAttachment.objects.filter(submission__student=user,submission__assignment__course__in=courses),"data","original_name"),
        ("revision",SubmissionRevision.objects.filter(submission__student=user,submission__assignment__course__in=courses,attachment_data__isnull=False),"attachment_data","attachment_name"),
        ("credential",CredentialArtifact.objects.filter(student__user=user,revocation__isnull=True),"pdf",None),
    ]
    selected=[];total=0
    for kind,query,field,name_field in specs:
        rows=list(query.defer(field).annotate(payload_size=Length(field)).order_by("pk")[:MAX_FILES+1])
        if len(rows)>MAX_FILES: raise ValidationError("Too many files for one archive. Contact records support.")
        for row in rows:
            if kind=="document" and not document_access(user,row.document): continue
            total+=row.payload_size or 0
            selected.append((kind,query,field,name_field,row.pk))
            if len(selected)>MAX_FILES or total>MAX_BYTES: raise ValidationError("Archive exceeds 500 files or 50 MB. Contact records support for a reviewed export.")
    output=tempfile.TemporaryFile()
    manifest=[];written=0
    try:
        with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_STORED) as archive:
            for kind,query,field,name_field,pk in selected:
                row=query.filter(pk=pk).first()
                if row is None or (kind=="document" and not document_access(user,row.document)): continue
                payload=bytes(getattr(row,field));written+=len(payload)
                if written>MAX_BYTES: raise ValidationError("Files changed beyond the export size limit. Try again later or contact records support.")
                digest=hashlib.sha256(payload).hexdigest()
                if kind in {"document","credential"} and digest!=row.sha256: raise ValidationError("A stored file failed its integrity check. Contact records support.")
                # User-supplied names are metadata only, never archive paths.
                path=f"{kind}/{pk}."+("pdf" if kind=="credential" else "bin")
                archive.writestr(path,payload)
                manifest.append({"path":path,"kind":kind,"record_id":pk,"original_name":getattr(row,name_field) if name_field else row.kind+".pdf","bytes":len(payload),"sha256":digest})
            archive.writestr("manifest.json",json.dumps({"format":"ftbi-personal-files-v1","exported_at":timezone.now().isoformat(),"files":manifest,"scope_notice":"Own currently accessible uploaded document versions, coursework attachments/revisions and unrevoked stored credentials only. No private staff notes, audit logs, other users' files or dynamically generated letters/certificates. Use the separate portal-record JSON export for record data; this is not a complete reviewed records request."},ensure_ascii=True,indent=2))
        output.seek(0)
        return output,len(manifest),written
    except Exception:
        output.close()
        raise


@login_required
@require_POST
def personal_files(request):
    if not cache.add(f"personal-file-export:{request.user.pk}",True,60):
        response=HttpResponse("Wait one minute before requesting another archive.",status=429)
        response["Retry-After"]="60"
        return response
    try: archive,count,size=build_archive(request.user)
    except ValidationError as exc: return HttpResponseForbidden(exc.messages[0])
    try:
        AuditEvent.objects.create(actor=request.user,action="personal_files_exported",target=str(request.user.pk))
        response=FileResponse(archive,as_attachment=True,filename="my-ftbi-files.zip",content_type="application/zip")
    except Exception:
        archive.close()
        raise
    response["Cache-Control"]="private, no-store";response["X-Content-Type-Options"]="nosniff"
    return response
