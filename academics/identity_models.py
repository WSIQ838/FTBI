from django.conf import settings
from django.db import models

class IdentityLink(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="institutional_identity")
    subject=models.CharField(max_length=255,unique=True,help_text="Immutable subject from the configured institutional identity provider.")
    def __str__(self):
        return str(self.user)
