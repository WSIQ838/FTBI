from django.conf import settings
from django.db import models
class RecoveryCode(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    digest=models.CharField(max_length=128)
