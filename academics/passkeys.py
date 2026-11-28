import secrets
from django.conf import settings
from django.db import models
from django_otp.models import Device


def user_handle(): return secrets.token_bytes(64)


class PasskeyIdentity(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    handle=models.BinaryField(default=user_handle,unique=True,editable=False)


class PasskeyDevice(Device):
    credential_id=models.CharField(max_length=1400,unique=True,editable=False)
    public_key=models.BinaryField(editable=False)
    sign_count=models.PositiveBigIntegerField(default=0)
    backed_up=models.BooleanField(default=False)
    backup_eligible=models.BooleanField(default=False)
    created=models.DateTimeField(auto_now_add=True)
    last_used=models.DateTimeField(null=True)
    revoked_at=models.DateTimeField(null=True)


class PasskeyChallenge(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    challenge=models.BinaryField(editable=False)
    session_digest=models.CharField(max_length=64)
    purpose=models.CharField(max_length=12)
    expires=models.DateTimeField()
    consumed=models.BooleanField(default=False)
    origin=models.CharField(max_length=300)
    rp_id=models.CharField(max_length=253)
    label=models.CharField(max_length=64,blank=True)
