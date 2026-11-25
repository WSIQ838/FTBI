from io import BytesIO
from html import escape
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from .transcripts import IssuedTranscript

@login_required
def transcript_pdf(request,identifier):
    records=IssuedTranscript.objects.all()
    if not (request.user.has_perm("academics.view_issuedtranscript") and request.user.has_perm("academics.view_studentprofile")):
        records=records.filter(request__student__user=request.user)
    record=get_object_or_404(records,identifier=identifier)
    snapshot=record.snapshot
    styles=getSampleStyleSheet()
    def p(value,style="BodyText"):
        return Paragraph(escape(str(value)),styles[style])
    story=[p(snapshot.get("institution",settings.FTBI_INSTITUTION_NAME),"Title"),p("Academic transcript","Heading1"),p(snapshot["name"]),p("Student number: "+str(snapshot["student_number"])),p("Program: "+str(snapshot["program"])),p("Issued: "+str(record.issued_at.date())),Spacer(1,16)]
    rows=[[p(x) for x in ["Course","Title","Term","Grade","Credits"]]]
    for course in snapshot["courses"]:
        rows.append([p(course[k]) for k in ["code","title","term","grade","credits"]])
    table=Table(rows,colWidths=[65,170,100,55,50],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,0),1,colors.black)]))
    story.extend([table,Spacer(1,16),p("Record ID: "+str(record.identifier)),p("Snapshot digest: "+record.digest),p("Not digitally signed. Verify authenticity with the registrar.")])
    output=BytesIO()
    SimpleDocTemplate(output,title="Academic transcript").build(story)
    output.seek(0)
    response=FileResponse(output,as_attachment=True,filename="transcript.pdf",content_type="application/pdf")
    response["Cache-Control"]="private, no-store"
    return response
