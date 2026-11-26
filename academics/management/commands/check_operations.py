import json
import logging
from django.core.management.base import BaseCommand,CommandError
from ftbi.observability import collect_metrics
from academics.monitoring import record_checks

class Command(BaseCommand):
    help="Collect bounded operational checks and record transition-only staff alerts."
    def handle(self,*args,**kwargs):
        payload=collect_metrics()
        try: record_checks(payload)
        except Exception:
            logging.getLogger("ftbi.operations").error("Operational alert persistence failed",extra={"event_code":"operation_alert_persistence_failed"})
            self.stdout.write(json.dumps(payload,sort_keys=True))
            raise CommandError("Operational checks could not persist alerts; external monitoring must inspect this failure.") from None
        self.stdout.write(json.dumps(payload,sort_keys=True))
        if not payload["healthy"]: raise CommandError("One or more operational checks require attention.")
