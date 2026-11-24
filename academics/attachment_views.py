from pathlib import PurePath
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,render,redirect
from django.http import HttpResponse,HttpResponseForbidden
from django.utils import timezone
from django.db import transaction
from django import forms
from django.utils.http import content_disposition_header
from .models import Submission,Enrollment
from .attachments import SubmissionAttachment

LIMIT=5*1024*1024
class AttachmentForm(forms.Form):
    file=forms.FileField(help_text="Plain text UTF-8 (.txt), maximum 5 MB. Other file formats are disabled pending malware scanning.")
    def clean_file(self):
        file=self.cleaned_data["file"]
        if file.size>LIMIT or file.size==0 or not file.name.lower().endswith(".txt"):
            raise forms.ValidationError("Upload a nonempty .txt file up to 5 MB.")
        data=file.read(LIMIT+1)
        if len(data)>LIMIT or b"\0" in data:
            raise forms.ValidationError("Invalid text file.")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise forms.ValidationError("File must be UTF-8 text.")
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
            locked=Submission.objects.select_for_update().get(pk=pk)
            if locked.grade is not None or timezone.now()>locked.assignment.due:
                return HttpResponseForbidden("Submission closed.")
            file=form.cleaned_data["file"]
            name=PurePath(file.name).name[:200]
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
