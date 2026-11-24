from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from .registrar import StudentProfile
from .models import Program

class FinancialAidAward(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    name=models.CharField(max_length=150)
    amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(0)])
    status=models.CharField(max_length=16,choices=[("pending","Pending"),("approved","Approved"),("disbursed","Disbursed"),("cancelled","Cancelled")],default="pending")
    visible=models.BooleanField(default=False)

class TransferCredit(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    institution=models.CharField(max_length=200)
    original_course=models.CharField(max_length=100)
    equivalent_code=models.CharField(max_length=30)
    credits=models.PositiveSmallIntegerField()
    approved=models.BooleanField(default=False)

class TranscriptRequest(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    destination=models.CharField(max_length=250)
    requested=models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=16,choices=[("pending","Pending"),("processing","Processing"),("issued","Issued"),("denied","Denied")],default="pending")

class Message(models.Model):
    sender=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="sent_messages")
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="received_messages")
    subject=models.CharField(max_length=160)
    body=models.TextField()
    sent=models.DateTimeField(auto_now_add=True)
    read=models.DateTimeField(null=True,blank=True)

class AuditEvent(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action=models.CharField(max_length=100)
    target=models.CharField(max_length=150)
    created=models.DateTimeField(auto_now_add=True)
