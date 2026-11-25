import copy
import hashlib
import uuid
from io import BytesIO
from html import escape
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
from reportlab.lib.pagesizes import letter,landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from .credentials import CredentialArtifact,CredentialTemplate,CredentialReplacement,verification_code
from .institution import institution_name
from .operations import AuditEvent

class CredentialSigningError(Exception): pass

def sign_pdf(data):
    """Offline signing only. Trust-chain and institutional certificate acceptance are external gates."""
    from pyhanko.sign import signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    try:
        if not settings.FTBI_SIGNING_P12_PATH or not settings.FTBI_SIGNING_P12_PASSWORD: raise ValueError("Missing signing material")
        signer=signers.SimpleSigner.load_pkcs12(settings.FTBI_SIGNING_P12_PATH,passphrase=settings.FTBI_SIGNING_P12_PASSWORD.encode())
        if signer is None: raise ValueError("Signer could not load")
        cert=x509.load_der_x509_certificate(signer.signing_cert.dump())
        if not cert.not_valid_before_utc<=timezone.now()<=cert.not_valid_after_utc: raise ValueError("Signing certificate is not current")
        usage=cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not usage.digital_signature and not usage.content_commitment: raise ValueError("Certificate cannot sign documents")
        writer=IncrementalPdfFileWriter(BytesIO(data))
        result=signers.sign_pdf(writer,signers.PdfSignatureMetadata(field_name="InstitutionSignature",md_algorithm="sha256",reason="Institution-issued academic credential"),signer=signer)
        return result.getvalue(),cert.fingerprint(hashes.SHA256()).hex()
    except Exception as error:
        raise CredentialSigningError("Credential signing failed; no credential was finalized.") from error

def render_credential(snapshot,kind,identifier,code,issued,signed):
    styles=getSampleStyleSheet()
    styles["BodyText"].fontSize=9
    styles["BodyText"].leading=11
    if kind=="diploma":
        for name in ["BodyText","Heading1","Heading2"]: styles[name].alignment=1
    def p(value,style="BodyText"): return Paragraph(escape(str(value)).replace("\n","<br/>"),styles[style])
    template=snapshot["template"]
    values={"recipient":snapshot["recipient"],"program":snapshot["program"],"institution":snapshot["institution"],"issued_date":str(issued.date()),"identifier":str(identifier)}
    story=[p(values["institution"],"Title"),Spacer(1,16),p(template["heading"].format_map(values),"Title"),Spacer(1,12),p(values["recipient"],"Heading1"),p(values["program"],"Heading2")]
    if template["body"]: story+=[p(template["body"].format_map(values)),Spacer(1,12)]
    if kind=="transcript":
        story.append(p("Student number: "+snapshot["student_number"]))
        rows=[[p(value) for value in ["Course","Title","Term","Grade","Credits"]]]
        rows += [[p(row[key]) for key in ["code","title","term","grade","credits"]] for row in snapshot["courses"]]
        table=Table(rows,colWidths=[65,190,110,65,60],repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e9eef4")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,0),1,colors.HexColor("#28445b"))]))
        story += [Spacer(1,12),table]
    verification=[Spacer(1,20),p("Issued: "+values["issued_date"]),p("Credential ID: "+str(identifier)),p("Verification code: "+code),p("Check current status at the institution's credential verification portal.")]
    if template["footer"]: verification.append(p(template["footer"].format_map(values)))
    verification.append(p("Digitally signed PDF. Validate the signature and certificate trust; registry revocation is separate." if signed else "Not digitally signed. Registry status is not a cryptographic signature."))
    story.append(KeepTogether(verification))
    stream=BytesIO()
    def page_footer(canvas,doc):
        canvas.saveState();canvas.setFont("Helvetica",7)
        canvas.drawString(36,20,str(identifier))
        canvas.drawRightString(doc.pagesize[0]-36,20,f"Page {doc.page}");canvas.restoreState()
    SimpleDocTemplate(stream,pagesize=landscape(letter) if kind=="diploma" else letter,leftMargin=36,rightMargin=36,topMargin=36,bottomMargin=36,title="Academic "+kind).build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return stream.getvalue()

@transaction.atomic
def seal_record(kind,record,actor,original=None,reason=""):
    # Serialize both first issuance and any replacement against the source row.
    record=type(record).objects.select_for_update().get(pk=record.pk)
    if original is None:
        existing=CredentialArtifact.objects.filter(identifier=record.identifier).first()
        if existing: return existing
        if kind=="transcript":
            snapshot=copy.deepcopy(record.snapshot); snapshot["recipient"]=snapshot["name"]; snapshot.setdefault("institution",institution_name())
            student=record.request.student
        else:
            snapshot={"recipient":record.recipient,"program":record.program,"institution":record.institution}; student=record.application.student
        template=CredentialTemplate.objects.filter(kind=kind,enabled=True).first()
        if template: template.full_clean()
        snapshot["template"]={"heading":template.heading if template else "Academic transcript" if kind=="transcript" else "Diploma","body":template.body if template else "","footer":template.footer if template else ""}
        identifier=record.identifier; issued=record.issued_at
    else:
        snapshot=copy.deepcopy(original.snapshot);student=original.student;identifier=uuid.uuid4();issued=timezone.now()
    code=verification_code();signed=settings.FTBI_CREDENTIAL_SIGNING_REQUIRED
    data=render_credential(snapshot,kind,identifier,code,issued,signed)
    fingerprint=""
    if signed: data,fingerprint=sign_pdf(data)
    artifact=CredentialArtifact.objects.create(identifier=identifier,student=student,kind=kind,snapshot=snapshot,pdf=data,sha256=hashlib.sha256(data).hexdigest(),verification_code=code,signed=signed,certificate_fingerprint=fingerprint,issued_by=actor,issued_at=issued,**{kind:record})
    if original: CredentialReplacement.objects.create(original=original,replacement=artifact,reason=reason)
    AuditEvent.objects.create(actor=actor,action="credential_reissued" if original else "credential_finalized",target=str(identifier))
    return artifact
