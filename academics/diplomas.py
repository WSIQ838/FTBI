import uuid
from django.conf import settings
from django.db import models
from .degree import GraduationApplication
class IssuedDiploma(models.Model):
    application=models.OneToOneField(GraduationApplication,on_delete=models.PROTECT)
    identifier=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    issued_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    issued_at=models.DateTimeField(auto_now_add=True)
    recipient=models.CharField(max_length=300)
    program=models.CharField(max_length=200)
    institution=models.CharField(max_length=200)
    def save(self,*args,**kwargs):
        if self.pk:
            raise ValueError("Issued diplomas cannot be modified.")
        super().save(*args,**kwargs)
