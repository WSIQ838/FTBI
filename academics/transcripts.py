import hashlib
import json
import uuid
from django.conf import settings
from django.db import models
from .operations import TranscriptRequest

class IssuedTranscript(models.Model):
    request=models.OneToOneField(TranscriptRequest,on_delete=models.PROTECT)
    identifier=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    issued_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    issued_at=models.DateTimeField(auto_now_add=True)
    snapshot=models.JSONField()
    digest=models.CharField(max_length=64,editable=False)
    def save(self,*args,**kwargs):
        if self.pk:
            raise ValueError("Issued transcript snapshots cannot be edited.")
        self.digest=hashlib.sha256(json.dumps(self.snapshot,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        super().save(*args,**kwargs)
