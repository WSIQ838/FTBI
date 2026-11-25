import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from .registrar import Application

class ApplicantActivation(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    nonce=models.UUIDField(default=uuid.uuid4)
    consumed=models.BooleanField(default=False)
    last_sent=models.DateTimeField(auto_now=True)

class ApplicationReviewer(models.Model):
    application=models.OneToOneField(Application,on_delete=models.PROTECT,related_name="review_assignment")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    assigned_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="admissions_assignments")
    updated=models.DateTimeField(auto_now=True)

class ApplicationNote(models.Model):
    application=models.ForeignKey(Application,on_delete=models.PROTECT,related_name="review_notes")
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    body=models.TextField(max_length=4000)
    created=models.DateTimeField(auto_now_add=True)

class AdmissionInterview(models.Model):
    application=models.ForeignKey(Application,on_delete=models.PROTECT,related_name="interviews")
    interviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    starts=models.DateTimeField()
    ends=models.DateTimeField()
    location=models.CharField(max_length=300)
    status=models.CharField(max_length=12,default="scheduled",choices=[("scheduled","Scheduled"),("cancelled","Cancelled")])
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="scheduled_interviews")
    created=models.DateTimeField(auto_now_add=True)

def reviewable(user):
    if not user.has_perm("academics.change_application"): return Application.objects.none()
    rows=Application.objects.all()
    if user.has_perm("academics.change_applicationreviewer"): return rows
    return rows.filter(Q(review_assignment__isnull=True)|Q(review_assignment__reviewer=user))
