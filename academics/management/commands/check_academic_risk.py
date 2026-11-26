import json
from django.core.management.base import BaseCommand
from academics.advising import AdvisorAssignment
from academics.risk_checks import check_assignment


class Command(BaseCommand):
    help="Queue deduplicated advisor alerts for latest recorded probation standing."
    def handle(self,*args,**options):
        checked=created=0
        assignments=AdvisorAssignment.objects.filter(active=True,student__status="active",advisor__is_active=True).order_by("pk").values_list("pk",flat=True)
        for assignment_id in assignments.iterator(chunk_size=200):
            created+=int(check_assignment(assignment_id))
            checked+=1
        self.stdout.write(json.dumps({"assignments_checked":checked,"alerts_created":created},sort_keys=True))
