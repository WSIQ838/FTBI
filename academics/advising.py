from django.conf import settings
from django.db import models
from .registrar import StudentProfile
class AdvisorAssignment(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT,related_name="advisor_assignments")
    advisor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    active=models.BooleanField(default=True)
    def __str__(self): return f"{self.advisor.get_full_name() or self.advisor.username} — {self.student.student_number}"
    class Meta:
        constraints=[models.UniqueConstraint(fields=["student","advisor"],name="unique_advisor_assignment")]
