import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from asn1crypto import x509 as asn1_x509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from .models import Department,Program
from .registrar import StudentProfile
from .operations import TranscriptRequest
from .transcripts import IssuedTranscript
from .degree import GraduationApplication
from .diplomas import IssuedDiploma
from .credentials import CredentialArtifact,CredentialTemplate,CredentialRevocation,CredentialReplacement
from .credential_service import seal_record


class CredentialTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.student=users.create_user("student")
        self.other=users.create_user("other")
        self.registrar=users.create_user("registrar",is_staff=True)
        self.registrar.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        program=Program.objects.create(name="Demonstration program",department=Department.objects.create(name="Credentials"))
        self.profile=StudentProfile.objects.create(user=self.student,program=program,student_number="S01",admitted_on=timezone.localdate())
        application=GraduationApplication.objects.create(student=self.profile,status="approved")
        self.diploma=IssuedDiploma.objects.create(application=application,issued_by=self.registrar,recipient="Synthetic Student",program=program.name,institution="Demonstration College")
        cache.clear()

    def test_exact_artifact_download_private_access_and_verification(self):
        artifact=seal_record("diploma",self.diploma,self.registrar)
        self.assertEqual(seal_record("diploma",self.diploma,self.registrar).pk,artifact.pk)
        self.assertEqual(artifact.sha256,hashlib.sha256(bytes(artifact.pdf)).hexdigest())
        with self.assertRaises(ValueError): artifact.save()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("credential_pdf",args=[artifact.identifier])).status_code,404)
        self.client.force_login(self.student)
        response=self.client.get(reverse("diploma_pdf",args=[self.diploma.identifier]))
        self.assertEqual(b"".join(response.streaming_content),bytes(artifact.pdf))
        self.client.logout()
        values={"identifier":str(artifact.identifier),"code":artifact.verification_code,"pdf":SimpleUploadedFile("credential.pdf",bytes(artifact.pdf))}
        response=self.client.post(reverse("verify_credential"),values)
        self.assertContains(response,"matches the finalized PDF")
        self.assertNotContains(response,"Synthetic Student")
        values["pdf"]=SimpleUploadedFile("modified.pdf",b"Changed file")
        self.assertContains(self.client.post(reverse("verify_credential"),values),"does not match")
        values.pop("pdf");values["code"]="incorrect"
        self.assertContains(self.client.post(reverse("verify_credential"),values),"could not be verified")

    def test_revocation_and_reissue_preserve_original_snapshot(self):
        original=seal_record("diploma",self.diploma,self.registrar)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("revoke_credential",args=[original.identifier]),{"reason":"Student attempt"}).status_code,403)
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(reverse("reissue_credential",args=[original.identifier]),{"reason":"Replacement"}).status_code,403)
        self.client.post(reverse("revoke_credential",args=[original.identifier]),{"reason":"Replace lost document"})
        for _ in range(2): self.assertEqual(self.client.post(reverse("reissue_credential",args=[original.identifier]),{"reason":"Replacement authorized"}).status_code,302)
        replacement=CredentialReplacement.objects.get().replacement
        self.assertNotEqual(original.identifier,replacement.identifier)
        self.assertEqual(original.snapshot,replacement.snapshot)
        self.assertEqual(CredentialArtifact.objects.count(),2)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("diploma_pdf",args=[self.diploma.identifier])).status_code,403)
        self.assertEqual(self.client.get(reverse("credential_pdf",args=[replacement.identifier])).status_code,200)
        self.client.logout()
        self.assertContains(self.client.post(reverse("verify_credential"),{"identifier":str(original.identifier),"code":original.verification_code}),"Revoked credential")

    @override_settings(FTBI_CREDENTIAL_SIGNING_REQUIRED=True,FTBI_SIGNING_P12_PATH="",FTBI_SIGNING_P12_PASSWORD="")
    def test_signing_failure_rolls_back_transcript_issuance(self):
        request=TranscriptRequest.objects.create(student=self.profile,destination="Personal copy")
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.post(reverse("issue_transcript",args=[request.pk])).status_code,503)
        request.refresh_from_db(); self.assertEqual(request.status,"pending")
        self.assertFalse(IssuedTranscript.objects.exists());self.assertFalse(CredentialArtifact.objects.exists())

    def test_templates_validate_placeholders_and_are_snapshotted(self):
        template=CredentialTemplate(kind="diploma",heading="Diploma",body="Awarded to {recipient} for {program}",footer="Approved institutional template",enabled=True,approval_reference="Synthetic approval")
        template.full_clean();template.save()
        artifact=seal_record("diploma",self.diploma,self.registrar)
        template.body="Updated body";template.save()
        self.assertIn("{recipient}",artifact.snapshot["template"]["body"])
        template.body="{recipient.__class__}"
        with self.assertRaises(ValidationError): template.full_clean()

    def test_real_pdf_signature_and_tamper_detection_with_ephemeral_certificate(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"FTBI synthetic signing test")])
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(timezone.now()-timedelta(hours=1)).not_valid_after(timezone.now()+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=True,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),critical=True).sign(key,hashes.SHA256()))
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.p12"
            path.write_bytes(pkcs12.serialize_key_and_certificates(b"synthetic",key,cert,None,serialization.BestAvailableEncryption(b"synthetic-signing-test-password")))
            with override_settings(FTBI_CREDENTIAL_SIGNING_REQUIRED=True,FTBI_SIGNING_P12_PATH=str(path),FTBI_SIGNING_P12_PASSWORD="synthetic-signing-test-password"):
                artifact=seal_record("diploma",self.diploma,self.registrar)
                request=TranscriptRequest.objects.create(student=self.profile,destination="Synthetic copy",status="issued")
                transcript=IssuedTranscript.objects.create(request=request,issued_by=self.registrar,snapshot={"name":"Synthetic Student","program":"Program","student_number":"S01","courses":[]})
                signed_transcript=seal_record("transcript",transcript,self.registrar)
        self.assertTrue(artifact.signed)
        root=asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
        reader=PdfFileReader(BytesIO(bytes(artifact.pdf)))
        status=validate_pdf_signature(reader.embedded_signatures[0],signer_validation_context=ValidationContext(trust_roots=[root],allow_fetching=False))
        self.assertTrue(status.intact);self.assertTrue(status.valid);self.assertTrue(status.trusted)
        transcript_reader=PdfFileReader(BytesIO(bytes(signed_transcript.pdf)))
        transcript_status=validate_pdf_signature(transcript_reader.embedded_signatures[0],signer_validation_context=ValidationContext(trust_roots=[root],allow_fetching=False))
        self.assertTrue(transcript_status.intact);self.assertTrue(transcript_status.valid)
        altered=bytes(artifact.pdf).replace(b"Academic diploma",b"Academic diplomx",1)
        self.assertNotEqual(altered,bytes(artifact.pdf))
        changed=PdfFileReader(BytesIO(altered))
        status=validate_pdf_signature(changed.embedded_signatures[0],signer_validation_context=ValidationContext(trust_roots=[root],allow_fetching=False))
        self.assertFalse(status.intact)
