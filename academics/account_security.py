from django.conf import settings
from django.db import models


class AccountSecurity(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    locked=models.BooleanField(default=False)
    locked_until=models.DateTimeField(null=True,blank=True)
    failures=models.PositiveIntegerField(default=0)
    last_failure=models.DateTimeField(null=True,blank=True)
    session_epoch=models.PositiveIntegerField(default=0)
    last_network=models.CharField(max_length=64,blank=True)


class AccountSession(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    label=models.CharField(max_length=200)
    created=models.DateTimeField(auto_now_add=True)
    last_seen=models.DateTimeField()
    expires=models.DateTimeField()
    revoked=models.BooleanField(default=False)


class SecurityIncident(models.Model):
    title=models.CharField(max_length=200)
    description=models.TextField(help_text="Use incident references, not passwords, tokens or unnecessary student records.")
    severity=models.CharField(max_length=12,choices=[(x,x.title()) for x in ["low","medium","high","critical"]])
    status=models.CharField(max_length=16,default="open",choices=[(x,x.title()) for x in ["open","investigating","contained","resolved"]])
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="security_incidents")
    created=models.DateTimeField(auto_now_add=True)
    updated=models.DateTimeField(auto_now=True)


class AccountControlEvent(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="account_controls")
    target=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="account_control_history")
    action=models.CharField(max_length=12)
    reason=models.CharField(max_length=500)
    created=models.DateTimeField(auto_now_add=True)
