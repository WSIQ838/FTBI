from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.core.mail import send_mail
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from academics.models import Assignment,Enrollment,Submission
from academics.operations import AuditEvent

class Command(BaseCommand):
    help="Send generic upcoming coursework reminders to enrolled users with institution-verified email addresses."
    def handle(self,*args,**options):
        if not settings.FTBI_EMAIL_REMINDERS:
            self.stdout.write("Email reminders disabled.")
            return
        if not settings.EMAIL_HOST or not settings.SMTP_CONFIGURED:
            raise CommandError("SMTP required")
        if not cache.add("ftbi-reminder-run",1,timeout=3600):
            raise CommandError("Reminder job already active or recently run")
        now=timezone.now()
        upcoming=Assignment.objects.filter(course__published=True,due__gte=now,due__lt=now+timedelta(days=2))
        count=0
        for assignment in upcoming.iterator():
            submitted=Submission.objects.filter(assignment=assignment).values("student_id")
            recipients=Enrollment.objects.filter(course=assignment.course,active=True,student__is_active=True).exclude(student_id__in=submitted).exclude(student__email="").select_related("student")
            for enrollment in recipients.iterator():
                target=f"{assignment.pk}:{enrollment.student_id}"
                if AuditEvent.objects.filter(action="course_reminder_sent",target=target).exists():
                    continue
                # No assignment titles, scores, or personal data in message content.
                send_mail("Academic portal reminder","You may have upcoming coursework. Sign in to your academic portal to review your deadlines.",settings.DEFAULT_FROM_EMAIL,[enrollment.student.email],fail_silently=False)
                AuditEvent.objects.create(actor=enrollment.student,action="course_reminder_sent",target=target)
                count+=1
        self.stdout.write(f"Reminders sent: {count}")
