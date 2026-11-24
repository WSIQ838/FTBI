from django.core.management.base import BaseCommand,CommandError
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

class Command(BaseCommand):
    help="Check basic deployment prerequisites; not a security certification."
    def handle(self,*args,**kwargs):
        errors=[]
        if settings.DEBUG: errors.append("DEBUG is enabled")
        if connection.vendor!="postgresql": errors.append("PostgreSQL is required")
        executor=MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            errors.append("Unapplied migrations")
        if "academics" in executor.loader.unmigrated_apps:
            errors.append("Academics has no versioned migrations")
        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            errors.append("Secure cookies are disabled")
        if errors: raise CommandError("; ".join(errors))
        self.stdout.write("Basic deployment checks passed; independent security review still required.")
