from datetime import timedelta
from smtplib import SMTPException
from django.core.management.base import BaseCommand,CommandError
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from academics.notification_models import DurableNotification,NotificationPreference


class Command(BaseCommand):
    help="Deliver pending generic email notices; private details remain in the portal."
    def add_arguments(self,parser): parser.add_argument("--limit",type=int,default=100)
    def handle(self,*args,**options):
        if not settings.SMTP_CONFIGURED: raise CommandError("Approved SMTP is not configured; no notifications sent.")
        if not 1<=options["limit"]<=1000: raise CommandError("Limit must be between 1 and 1000.")
        ids=list(DurableNotification.objects.filter(email_status="pending",next_attempt__lte=timezone.now()).order_by("pk").values_list("pk",flat=True)[:options["limit"]])
        delivered=0
        for pk in ids:
            with transaction.atomic():
                notice=DurableNotification.objects.select_for_update().select_related("user").get(pk=pk)
                if notice.email_status!="pending" or notice.next_attempt>timezone.now(): continue
                enabled=not NotificationPreference.objects.filter(user=notice.user,email_enabled=False).exists()
                if not enabled or not notice.user.email or not notice.user.is_active:
                    notice.email_status="skipped"; notice.save(update_fields=["email_status"]); continue
                notice.email_attempts+=1
                try:
                    sent=send_mail("FTBI account notification","There is a new update in your FTBI account. Sign in through your institution's usual portal to review it. Do not reply with personal records or passwords.",settings.DEFAULT_FROM_EMAIL,[notice.user.email],fail_silently=False)
                    if sent!=1: raise OSError("Mail backend did not accept the notification")
                except (SMTPException,OSError,ValueError):
                    notice.email_status="failed" if notice.email_attempts>=5 else "pending"
                    notice.next_attempt=timezone.now()+timedelta(minutes=2**notice.email_attempts)
                else:
                    notice.email_status="sent"; notice.sent_at=timezone.now(); delivered+=1
                notice.save()
        self.stdout.write(f"Notifications sent: {delivered}")
