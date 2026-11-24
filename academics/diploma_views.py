from io import BytesIO
from xml.sax.saxutils import escape
from django.conf import settings
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.http import FileResponse,HttpResponseForbidden
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_POST
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.pagesizes import landscape,letter
from reportlab.lib.styles import getSampleStyleSheet
from .degree import GraduationApplication
from .degree_views import audit
from .diplomas import IssuedDiploma
from .operations import AuditEvent

@login_required
@permission_required("academics.add_issueddiploma",raise_exception=True)
@permission_required("academics.change_graduationapplication",raise_exception=True)
@permission_required("academics.view_finalgrade",raise_exception=True)
def diploma_queue(request):
    return render(request,"diploma_queue.html",{"applications":GraduationApplication.objects.filter(status="approved",student__status="graduated",issueddiploma__isnull=True).select_related("student__user","student__program")})

@login_required
@permission_required("academics.add_issueddiploma",raise_exception=True)
@permission_required("academics.change_graduationapplication",raise_exception=True)
@permission_required("academics.view_finalgrade",raise_exception=True)
@require_POST
def issue_diploma(request,pk):
    with transaction.atomic():
        application=get_object_or_404(GraduationApplication.objects.select_for_update(),pk=pk)
        student=application.student
        if application.status!="approved" or student.status!="graduated" or not audit(student)["eligible"]:
            return HttpResponseForbidden("Graduation and eligibility must be confirmed.")
        record,created=IssuedDiploma.objects.get_or_create(application=application,defaults={"issued_by":request.user,"recipient":student.user.get_full_name() or student.user.username,"program":student.program.name,"institution":settings.FTBI_INSTITUTION_NAME[:200]})
        if created:
            AuditEvent.objects.create(actor=request.user,action="diploma_issued",target=str(record.identifier))
    return redirect("diploma_pdf",identifier=record.identifier)

@login_required
def diploma_pdf(request,identifier):
    records=IssuedDiploma.objects.all()
    if not request.user.has_perms(["academics.view_issueddiploma","academics.view_studentprofile"]):
        records=records.filter(application__student__user=request.user)
    record=get_object_or_404(records,identifier=identifier)
    styles=getSampleStyleSheet()
    def p(value,style="Normal"):
        return Paragraph(escape(str(value)),styles[style])
    story=[p(record.institution,"Title"),Spacer(1,40),p("Diploma","Title"),p("This document records the award to","Normal"),Spacer(1,18),p(record.recipient,"Title"),p(record.program,"Title"),Spacer(1,24),p("Issued "+str(record.issued_at.date())),p("Record ID: "+str(record.identifier)),p("Not digitally signed. Verify with the issuing registrar.")]
    stream=BytesIO()
    SimpleDocTemplate(stream,pagesize=landscape(letter),title="Diploma").build(story)
    stream.seek(0)
    response=FileResponse(stream,as_attachment=True,filename="diploma.pdf",content_type="application/pdf")
    response["Cache-Control"]="private, no-store"
    return response
