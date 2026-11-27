"""Plain-text institution wording, captured at issuance; no executable templates."""
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .credentials import CredentialTemplate

DEFAULT_TEMPLATE={"heading":"Enrollment verification","body":"","footer":""}


def template_snapshot():
    template=CredentialTemplate.objects.filter(kind="enrollment",enabled=True).first()
    if template is None: return dict(DEFAULT_TEMPLATE)
    template.full_clean()
    return {"heading":template.heading,"body":template.body,"footer":template.footer,
            "approval_reference":template.approval_reference,"template_id":template.pk}


def render_letter(snapshot,identifier,issued):
    styles=getSampleStyleSheet()
    styles["BodyText"].fontSize=10
    styles["BodyText"].leading=14
    def paragraph(value,style="BodyText"):
        return Paragraph(escape(str(value)).replace("\n","<br/>"),styles[style])
    values={"recipient":snapshot["name"],"program":snapshot.get("program",""),
            "institution":snapshot["institution"],"issued_date":str(issued.date()),"identifier":str(identifier)}
    template=snapshot.get("template",DEFAULT_TEMPLATE)
    story=[paragraph(values["institution"],"Title"),Spacer(1,12),
           paragraph(template["heading"].format_map(values),"Heading1"),
           paragraph(values["recipient"]),paragraph("Student number: "+snapshot["student_number"])]
    if values["program"]: story.append(paragraph("Program: "+values["program"]))
    if template["body"]: story.extend([Spacer(1,12),paragraph(template["body"].format_map(values))])
    rows=[[paragraph(label,"Heading3") for label in ["Course","Title","Term"]]]
    rows += [[paragraph(row[key]) for key in ["course__code","course__title","course__term__name"]] for row in snapshot["enrollments"]]
    table=Table(rows,colWidths=[75,285,180],repeatRows=1,hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e9eef4")),
                              ("VALIGN",(0,0),(-1,-1),"TOP"),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story.extend([Spacer(1,16),table,Spacer(1,16),paragraph("Issued: "+values["issued_date"]),
                  paragraph("Record ID: "+str(identifier))])
    if template["footer"]: story.append(paragraph(template["footer"].format_map(values)))
    story.append(paragraph("Snapshot of active enrollments at issuance. Not digitally signed."))
    def page_footer(canvas,document):
        canvas.saveState();canvas.setFont("Helvetica",7)
        canvas.drawString(36,20,str(identifier));canvas.drawRightString(576,20,f"Page {document.page}")
        canvas.restoreState()
    stream=BytesIO()
    SimpleDocTemplate(stream,pagesize=letter,leftMargin=36,rightMargin=36,topMargin=36,bottomMargin=36,
                      title="Enrollment verification").build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return stream.getvalue()
