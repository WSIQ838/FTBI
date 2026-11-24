from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationPreference(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    email_enabled=models.BooleanField(default=True)


class DurableNotification(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    category=models.CharField(max_length=40)
    subject=models.CharField(max_length=160)
    body=models.TextField()
    deduplication_key=models.CharField(max_length=200,unique=True)
    created=models.DateTimeField(auto_now_add=True)
    read_at=models.DateTimeField(null=True,blank=True)
    email_status=models.CharField(max_length=12,default="pending",choices=[("pending","Pending"),("sent","Sent"),("skipped","Skipped"),("failed","Failed")])
    email_attempts=models.PositiveSmallIntegerField(default=0)
    next_attempt=models.DateTimeField(default=timezone.now)
    sent_at=models.DateTimeField(null=True,blank=True)


def notify(user,category,subject,body,key):
    return DurableNotification.objects.get_or_create(deduplication_key=key,defaults={"user":user,"category":category,"subject":subject,"body":body})[0]
