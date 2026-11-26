import json
import logging
import subprocess
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import TestCase,SimpleTestCase,override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.utils import timezone
from django.core.management import call_command,CommandError
from ftbi.observability import SafeJSONFormatter,backup_health,collect_metrics
from .monitoring import OperationAlert,record_checks
from .notification_models import DurableNotification
from scripts import backup_catalog as catalog


class BackupCatalogTests(SimpleTestCase):
    def managed(self,root,index,age=0):
        name=f"ftbi-20260101T00000{index}Z-test.dump.age"
        (root/name).write_bytes(b"SYNTHETIC encrypted archive fixture "+str(index).encode())
        entry=catalog.record(root,name)
        entry["created"]=(timezone.now()-timedelta(days=age)).isoformat()
        catalog.atomic_json(root/(name+".json"),entry)
        return name

    def test_retention_requires_verified_newer_backup_and_defaults_to_dry_run(self):
        with TemporaryDirectory() as directory:
            root=catalog.initialize(directory)
            old=self.managed(root,0,60);middle=self.managed(root,1,50);newer=self.managed(root,2,5);latest=self.managed(root,3,0)
            unmanaged=root/"unrelated.txt";unmanaged.write_text("preserve",encoding="utf-8")
            self.assertEqual(catalog.prune(root,30,2)["candidates"],[])
            catalog.mark_restored(root,latest)
            plan=catalog.prune(root,30,2)
            self.assertEqual(set(plan["candidates"]),{old,middle});self.assertTrue((root/old).exists())
            catalog.prune(root,30,2,apply=True)
            self.assertFalse((root/old).exists());self.assertTrue((root/newer).exists());self.assertTrue(unmanaged.exists())

    def test_corruption_or_unmanaged_directory_blocks_retention(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): catalog.prune(directory)
            root=catalog.initialize(directory);name=self.managed(root,0)
            (root/name).write_bytes(b"tampered")
            with self.assertRaises(ValueError): catalog.prune(root,7,2,apply=True)
            self.assertTrue((root/name).exists())
            with self.assertRaises(ValueError): catalog.archive_path(root,"../escape.dump.age")
            with self.assertRaises(ValueError): catalog.prune(root,1,1,apply=True)

    def test_symlinks_and_overlapping_catalog_work_are_rejected(self):
        with TemporaryDirectory() as directory:
            root=catalog.initialize(directory)
            with catalog.locked(root):
                with self.assertRaises(FileExistsError): catalog.prune(root)
            name=self.managed(root,0)
            target=root/"outside";target.write_bytes(b"private unrelated data")
            (root/name).unlink()
            try: (root/name).symlink_to(target)
            except OSError: self.skipTest("Creating symlinks requires host privileges")
            with self.assertRaises(ValueError): catalog.inventory(root)
            self.assertTrue(target.exists())

    def test_failed_backup_records_generic_status_without_provider_error(self):
        with TemporaryDirectory() as directory:
            root=catalog.initialize(directory)
            with patch("scripts.backup_catalog.subprocess.run",side_effect=subprocess.CalledProcessError(1,"synthetic",stderr="SECRET")):
                with self.assertRaisesRegex(RuntimeError,"Encrypted backup failed"): catalog.run_backup(root)
            data=(root/".backup-status.json").read_text(encoding="utf-8")
            self.assertNotIn("SECRET",data);self.assertEqual(json.loads(data)["result"],"failed")
            self.assertFalse((root/".catalog.lock").exists())


class MonitoringTests(TestCase):
    def test_metrics_require_header_token_and_report_dependency_failure(self):
        url=reverse("operation_metrics")
        self.assertEqual(self.client.get(url).status_code,404)
        payload={"healthy":False,"checks":{"database":False},"metrics":{}}
        with override_settings(FTBI_MONITOR_TOKEN="synthetic-monitor-token-at-least-32-characters"),patch("ftbi.observability.collect_metrics",return_value=payload):
            self.assertEqual(self.client.get(url+"?token=synthetic-monitor-token-at-least-32-characters").status_code,401)
            self.assertEqual(self.client.get(url,HTTP_AUTHORIZATION="Bearer wrong").status_code,401)
            self.assertEqual(self.client.get(url,HTTP_AUTHORIZATION="Bearer nonascii-é").status_code,401)
            response=self.client.get(url,HTTP_AUTHORIZATION="Bearer synthetic-monitor-token-at-least-32-characters")
            self.assertEqual(response.status_code,503);self.assertEqual(response["Cache-Control"],"private, no-store")

    def test_alerts_notify_once_per_transition_and_dashboard_requires_role(self):
        user=get_user_model().objects.create_user("operator",is_staff=True)
        group=Group.objects.create(name="Operations");user.groups.add(group)
        group.permissions.add(Permission.objects.get(codename="view_operationalert"))
        payload={"healthy":False,"checks":{"backup":False}}
        record_checks(payload);record_checks(payload)
        self.assertEqual(DurableNotification.objects.count(),1)
        self.assertEqual(OperationAlert.objects.get(code="backup").occurrences,2)
        record_checks({"healthy":True,"checks":{"backup":True}})
        self.assertEqual(DurableNotification.objects.count(),2)
        self.assertFalse(OperationAlert.objects.get(code="backup").active)
        self.client.force_login(user)
        with patch("academics.monitoring_views.collect_metrics",return_value=payload): self.assertEqual(self.client.get(reverse("operations")).status_code,200)
        self.client.force_login(get_user_model().objects.create_user("other"))
        self.assertEqual(self.client.get(reverse("operations")).status_code,403)

    def test_backup_freshness_failure_and_disabled_settings(self):
        with override_settings(FTBI_BACKUP_DIR=""): self.assertEqual(backup_health()["state"],"unconfigured")
        with TemporaryDirectory() as directory,override_settings(FTBI_BACKUP_DIR=directory,FTBI_BACKUP_MAX_AGE_HOURS=26):
            root=catalog.initialize(directory)
            data={"result":"success","last_success":timezone.now().isoformat(),"last_attempt":timezone.now().isoformat()}
            catalog.atomic_json(root/".backup-status.json",data)
            self.assertTrue(backup_health()["healthy"])
            data["result"]="running";catalog.atomic_json(root/".backup-status.json",data)
            self.assertTrue(backup_health()["healthy"])
            data["last_attempt"]=(timezone.now()-timedelta(hours=2)).isoformat();catalog.atomic_json(root/".backup-status.json",data)
            self.assertFalse(backup_health()["healthy"])
            data["result"]="failed";catalog.atomic_json(root/".backup-status.json",data)
            self.assertFalse(backup_health()["healthy"])
            data.update(result="success",last_success=(timezone.now()-timedelta(hours=27)).isoformat());catalog.atomic_json(root/".backup-status.json",data)
            self.assertFalse(backup_health()["healthy"])

    def test_metrics_surface_failed_notifications_and_command_failure(self):
        user=get_user_model().objects.create_user("student")
        DurableNotification.objects.create(user=user,category="test",subject="Private",body="Do not expose",deduplication_key="test",email_status="failed")
        with patch("ftbi.observability.backup_health",return_value={"healthy":True,"state":"healthy"}):
            payload=collect_metrics()
        self.assertFalse(payload["checks"]["notifications"])
        self.assertEqual(payload["metrics"]["failed_notifications"],1)
        self.assertNotIn("Do not expose",json.dumps(payload))
        with patch("academics.management.commands.check_operations.collect_metrics",return_value=payload),patch("academics.management.commands.check_operations.record_checks",side_effect=RuntimeError("SECRET")):
            with self.assertRaisesRegex(CommandError,"could not persist"): call_command("check_operations",stdout=StringIO())

    def test_json_logging_omits_secrets_request_values_and_exception_messages(self):
        record=logging.LogRecord("ftbi.test",logging.ERROR,"private/path",1,"password=%s",("SECRET",),None)
        record.event_code="operational_failure"
        record.request={"authorization":"TOKEN"}
        record.exc_info=(ValueError,ValueError("PRIVATE RECORD"),None)
        data=SafeJSONFormatter().format(record)
        for secret in ["SECRET","TOKEN","PRIVATE RECORD","private/path","password"]: self.assertNotIn(secret,data)
        self.assertEqual(json.loads(data)["exception_type"],"ValueError")
