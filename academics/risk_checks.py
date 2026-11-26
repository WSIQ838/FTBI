"""Repeat-safe support alerts derived only from recorded academic standing."""
from django.db import transaction
from .advising import AdvisorAssignment
from .student_records import AcademicStanding
from .student_support import AtRiskAlert
from .notification_models import notify
from .operations import AuditEvent


@transaction.atomic
def check_assignment(assignment_id,actor=None):
    assignment=AdvisorAssignment.objects.select_for_update().filter(pk=assignment_id,active=True,student__status="active",advisor__is_active=True).first()
    if not assignment or not assignment.advisor.has_perm("academics.view_advisorassignment"): return False
    standing=AcademicStanding.objects.filter(student=assignment.student).order_by("-term__ends","-created","-pk").first()
    if not standing or standing.status!="probation": return False
    alert,created=AtRiskAlert.objects.get_or_create(standing=standing,advisor=assignment.advisor)
    if created:
        AuditEvent.objects.create(actor=actor,action="academic_risk_flagged",target=str(alert.pk))
        notify(assignment.advisor,"enrollment","Academic support review needed","Review standing alerts in your private student support workspace.",f"risk-alert:{alert.pk}")
    return created
