from .credential_service import seal_record,CredentialSigningError
from .credentials import CredentialArtifact
from .institution import institution_name
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.http import HttpResponseForbidden,HttpResponse
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_POST
from .operations import TranscriptRequest,AuditEvent
from .transcripts import IssuedTranscript
from .services import FinalGrade

@login_required
@permission_required("academics.change_transcriptrequest",raise_exception=True)
@permission_required("academics.add_issuedtranscript",raise_exception=True)
@permission_required("academics.view_finalgrade",raise_exception=True)
@require_POST
def issue(request,pk):
    with transaction.atomic():
        item=get_object_or_404(TranscriptRequest.objects.select_for_update(),pk=pk)
        if item.status not in ("pending","processing"):
            return HttpResponseForbidden("Request cannot be issued.")
        student=item.student
        grades=FinalGrade.objects.filter(student=student,released=True).select_related("course","course__term").order_by("course__term__starts","course__code")
        snapshot={"institution":institution_name(),"name":student.user.get_full_name() or student.user.username,"student_number":student.student_number,"program":str(student.program),"courses":[{"code":g.course.code,"title":g.course.title,"term":str(g.course.term),"grade":g.letter,"credits":g.credits_earned} for g in grades]}
        record=IssuedTranscript.objects.create(request=item,issued_by=request.user,snapshot=snapshot)
        try: seal_record("transcript",record,request.user)
        except CredentialSigningError:
            transaction.set_rollback(True)
            return HttpResponse("Credential signing is unavailable. No transcript was issued.",status=503)
        item.status="issued"
        item.save(update_fields=["status"])
        AuditEvent.objects.create(actor=request.user,action="transcript_issued",target=str(record.identifier))
    return redirect("transcript",identifier=record.identifier)

@login_required
def transcript(request,identifier):
    records=IssuedTranscript.objects.all()
    if not (request.user.has_perm("academics.view_issuedtranscript") and request.user.has_perm("academics.view_studentprofile")):
        records=records.filter(request__student__user=request.user)
    record=get_object_or_404(records,identifier=identifier)
    response=render(request,"transcript.html",{"record":record,"artifact":CredentialArtifact.objects.filter(identifier=record.identifier).first()})
    response["Cache-Control"]="no-store, private"
    return response

@login_required
@permission_required("academics.change_transcriptrequest",raise_exception=True)
@permission_required("academics.add_issuedtranscript",raise_exception=True)
def transcript_queue(request):
    return render(request,"transcript_queue.html",{"items":TranscriptRequest.objects.filter(status__in=["pending","processing"]).select_related("student","student__user")})
