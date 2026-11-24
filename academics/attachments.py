from django.db import models
from django.conf import settings
from .models import Submission

class SubmissionAttachment(models.Model):
    submission=models.OneToOneField(Submission,on_delete=models.CASCADE,related_name="attachment")
    original_name=models.CharField(max_length=200)
    data=models.BinaryField(editable=False)
    size=models.PositiveIntegerField()
    uploaded=models.DateTimeField(auto_now=True)
