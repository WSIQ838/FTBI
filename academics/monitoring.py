from django.db import models,transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from .operations import AuditEvent
from .notification_models import notify


class OperationAlert(models.Model):
    code=models.CharField(max_length=40,unique=True)
    active=models.BooleanField(default=False)
    first_seen=models.DateTimeField(null=True)
    last_checked=models.DateTimeField()
    changed=models.DateTimeField(null=True)
    occurrences=models.PositiveIntegerField(default=0)


@transaction.atomic
def record_checks(payload):
    # A single fixed row serializes monitor runs, including first-time alert creation.
    lock,_=OperationAlert.objects.get_or_create(code="monitor",defaults={"last_checked":timezone.now()})
    OperationAlert.objects.select_for_update().get(pk=lock.pk)
    recipients=get_user_model().objects.filter(is_staff=True,is_active=True,groups__name="Operations").distinct()
    for code,healthy in payload["checks"].items():
        if code not in {"database","cache","disk","backup","notifications"}: continue
        alert,_=OperationAlert.objects.get_or_create(code=code,defaults={"last_checked":timezone.now()})
        active=not healthy;changed=alert.active!=active
        alert.last_checked=timezone.now()
        if active:
            alert.occurrences+=1
            if not alert.first_seen: alert.first_seen=timezone.now()
        if changed:
            alert.active=active;alert.changed=timezone.now()
            if not active: alert.first_seen=None
            event=AuditEvent.objects.create(action="operation_alert_opened" if active else "operation_alert_resolved",target=code)
            for user in recipients:
                notify(user,"operations","FTBI operational alert" if active else "FTBI operational recovery",f"Operational check {code} {'requires attention' if active else 'has recovered'}. Review the private Operations workspace.",f"operation-alert:{event.pk}:{user.pk}")
        alert.save()
    lock.last_checked=timezone.now();lock.save(update_fields=["last_checked"])
