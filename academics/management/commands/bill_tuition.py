from django.core.management.base import BaseCommand
from academics.billing import TuitionSchedule,bill_schedule


class Command(BaseCommand):
    help="Issue idempotent tuition invoices for active schedules and active enrollments."
    def handle(self,*args,**kwargs):
        count=sum(bill_schedule(schedule) for schedule in TuitionSchedule.objects.filter(active=True))
        self.stdout.write(f"Invoices issued: {count}")
