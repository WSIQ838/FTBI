from django.conf import settings
from django.db import models
from .registrar import StudentProfile
class AdvisorAssignment(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT,related_name="advisor_assignments")
    advisor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","advisor"],name="unique_advisor_assignment")]
