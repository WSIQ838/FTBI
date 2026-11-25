from django.conf import settings
from .scanning import scan_clean
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from pathlib import PurePath
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,render,redirect
from django.http import HttpResponse,HttpResponseForbidden
from django.utils import timezone
from django.db import transaction
from django import forms
from django.utils.http import content_disposition_header
from .models import Submission,Enrollment,Assignment
from .assessment_policy import submission_open
from .attachments import SubmissionAttachment

LIMIT=5*1024*1024
class AttachmentForm(forms.Form):
    file=forms.FileField(help_text="Maximum 5 MB. Text files are supported; PDF, images and Office documents require an enabled malware scanner.")
    def clean_file(self):
        file=self.cleaned_data["file"]
        ext=PurePath(file.name).suffix.lower()
        if file.size>LIMIT or file.size==0:
            raise forms.ValidationError("Upload a nonempty file up to 5 MB.")
        data=file.read(LIMIT+1)
        if len(data)>LIMIT:
            raise forms.ValidationError("File too large.")
        if ext==".txt":
            try:
                if b"\0" in data:
                    raise ValueError()
                data.decode("utf-8")
            except ValueError:
                raise forms.ValidationError("File must be UTF-8 text.")
        else:
            if not settings.FTBI_CLAMAV_HOST:
                raise forms.ValidationError("Document uploads are disabled.")
            signatures={".pdf":b"%PDF-",".png":b"\x89PNG\r\n\x1a\n",".jpg":b"\xff\xd8\xff",".jpeg":b"\xff\xd8\xff"}
            office={".docx":"word/document.xml",".xlsx":"xl/workbook.xml",".pptx":"ppt/presentation.xml"}
            valid=ext in signatures and data.startswith(signatures[ext])
            if ext in office:
                try:
                    with ZipFile(BytesIO(data)) as archive:
                        entries=archive.infolist()
                        names=set(archive.namelist())
                        valid=len(entries)<=2000 and sum(e.file_size for e in entries)<=50*1024*1024 and office[ext] in names and "[Content_Types].xml" in names and not any("vbaproject" in n.lower() for n in names)
                except (BadZipFile,ValueError,OSError):
                    valid=False
            if not valid:
                raise forms.ValidationError("Unsupported or invalid document.")
        if settings.FTBI_CLAMAV_HOST and not scan_clean(data):
            raise forms.ValidationError("File rejected or scanning service unavailable.")
        self.payload=data
        return file

@login_required
def upload_attachment(request,pk):
    submission=get_object_or_404(Submission,pk=pk,student=request.user,assignment__course__published=True)
    if not Enrollment.objects.filter(student=request.user,course=submission.assignment.course,active=True).exists():
        return HttpResponseForbidden()
    form=AttachmentForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            Assignment.objects.select_for_update().get(pk=submission.assignment_id)
            locked=Submission.objects.select_for_update().get(pk=pk)
            if not submission_open(locked.assignment, locked, attachment=True):
                return HttpResponseForbidden("Submission closed.")
            file=form.cleaned_data["file"]
            name=PurePath(file.name).name[:200]
            from django.contrib.auth import get_user_model
            from .documents import StorageQuota,storage_used
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            quota=getattr(StorageQuota.objects.filter(user=request.user).first(),"limit_bytes",104857600)
            previous=SubmissionAttachment.objects.filter(submission=locked).first()
            if storage_used(request.user)-(previous.size if previous else 0)+len(form.payload)>quota:
                return HttpResponseForbidden("Storage quota exceeded. Contact records support.")
            SubmissionAttachment.objects.update_or_create(submission=locked,defaults={"original_name":name,"data":form.payload,"size":len(form.payload)})
        return redirect("course",pk=submission.assignment.course_id)
    return render(request,"attachment.html",{"form":form,"submission":submission})

@login_required
def download_attachment(request,pk):
    attachment=get_object_or_404(SubmissionAttachment.objects.select_related("submission__assignment__course"),submission_id=pk)
    submission=attachment.submission
    course=submission.assignment.course
    if course.instructor_id!=request.user.pk and not (submission.student_id==request.user.pk and course.published and Enrollment.objects.filter(student=request.user,course=course,active=True).exists()):
        from django.http import Http404
        raise Http404()
    response=HttpResponse(bytes(attachment.data),content_type="application/octet-stream")
    response["Content-Disposition"]=content_disposition_header(True,attachment.original_name)
    response["X-Content-Type-Options"]="nosniff"
    response["Cache-Control"]="private, no-store"
    return response
