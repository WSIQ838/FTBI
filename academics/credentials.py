import secrets
import uuid
from string import Formatter
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from .registrar import StudentProfile
from .transcripts import IssuedTranscript
from .diplomas import IssuedDiploma

def verification_code(): return secrets.token_urlsafe(24)

class CredentialTemplate(models.Model):
    kind=models.CharField(max_length=12,unique=True,choices=[("transcript","Transcript"),("diploma","Diploma")])
    heading=models.CharField(max_length=100)
    body=models.TextField(max_length=2000,blank=True)
    footer=models.CharField(max_length=500,blank=True)
    enabled=models.BooleanField(default=False)
    approval_reference=models.CharField(max_length=200)
    def clean(self):
        allowed={"recipient","program","institution","issued_date","identifier"}
        try:
            for text in [self.heading,self.body,self.footer]:
                for _,field,spec,conversion in Formatter().parse(text):
                    if field is not None and (field not in allowed or spec or conversion): raise ValueError()
        except ValueError: raise ValidationError("Use only plain placeholders: recipient, program, institution, issued_date, identifier.")

class CredentialArtifact(models.Model):
    identifier=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    kind=models.CharField(max_length=12,choices=[("transcript","Transcript"),("diploma","Diploma")])
    transcript=models.ForeignKey(IssuedTranscript,on_delete=models.PROTECT,null=True,related_name="credential_artifacts")
    diploma=models.ForeignKey(IssuedDiploma,on_delete=models.PROTECT,null=True,related_name="credential_artifacts")
    snapshot=models.JSONField()
    pdf=models.BinaryField(editable=False)
    sha256=models.CharField(max_length=64)
    verification_code=models.CharField(max_length=40,default=verification_code,editable=False)
    signed=models.BooleanField(default=False)
    certificate_fingerprint=models.CharField(max_length=64,blank=True)
    issued_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    issued_at=models.DateTimeField()
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(kind="transcript",transcript__isnull=False,diploma__isnull=True)|models.Q(kind="diploma",diploma__isnull=False,transcript__isnull=True)),name="credential_source_matches_kind")]
    def save(self,*args,**kwargs):
        if self.pk: raise ValueError("Credential artifacts are immutable.")
        super().save(*args,**kwargs)

class CredentialRevocation(models.Model):
    credential=models.OneToOneField(CredentialArtifact,on_delete=models.PROTECT,related_name="revocation")
    reason=models.TextField(max_length=2000)
    revoked_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    revoked_at=models.DateTimeField(auto_now_add=True)

class CredentialReplacement(models.Model):
    original=models.OneToOneField(CredentialArtifact,on_delete=models.PROTECT,related_name="replacement")
    replacement=models.OneToOneField(CredentialArtifact,on_delete=models.PROTECT,related_name="replaces")
    reason=models.TextField(max_length=2000)
    created=models.DateTimeField(auto_now_add=True)
