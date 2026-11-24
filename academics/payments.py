from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from .registrar import StudentProfile

class PaymentRequest(models.Model):
    ledger=models.OneToOneField("academics.LedgerEntry",on_delete=models.PROTECT,null=True,blank=True,related_name="payment_record")
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(1)])
    created=models.DateTimeField(auto_now_add=True)
    reference=models.CharField(max_length=200,blank=True)
    status=models.CharField(max_length=16,choices=[("pending","Pending review"),("verified","Verified"),("rejected","Rejected")],default="pending")
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
