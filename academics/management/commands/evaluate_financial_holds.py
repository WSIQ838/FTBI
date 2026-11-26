from django.core.management.base import BaseCommand
from academics.registrar import StudentProfile
from academics.finance_adjustments import evaluate_financial_hold

class Command(BaseCommand):
    help="Reevaluate automatic holds under the approved policy; preserve manual registration holds."
    def handle(self,*args,**kwargs):
        active=0;count=0
        for student in StudentProfile.objects.order_by("pk").iterator():
            active+=evaluate_financial_hold(student).active;count+=1
        self.stdout.write(f"Evaluated {count} accounts; {active} automatic financial holds active.")
