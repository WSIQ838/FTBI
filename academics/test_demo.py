import os
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from .models import Enrollment,Course


class DemoTests(TestCase):
    @override_settings(DEBUG=False)
    def test_demo_refuses_production(self):
        with patch.dict(os.environ,{"FTBI_ALLOW_DEMO":"1","FTBI_DEMO_PASSWORD":"synthetic-only-demo-password"}):
            with self.assertRaises(CommandError): call_command("seed_demo")
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(DEBUG=True)
    def test_demo_generates_synthetic_roles_and_refuses_existing_records(self):
        with patch.dict(os.environ,{"FTBI_ALLOW_DEMO":"1","FTBI_DEMO_PASSWORD":"synthetic-only-demo-password"}):
            call_command("seed_demo")
            self.assertEqual(Enrollment.objects.count(),5)
            self.assertEqual(Course.objects.get().lessons.count(),1)
            self.assertFalse(get_user_model().objects.filter(is_staff=True).exists())
            with self.assertRaises(CommandError): call_command("seed_demo")
            self.assertEqual(get_user_model().objects.count(),7)

    @override_settings(DEBUG=True)
    def test_browser_records_fixture_has_scoped_review_permissions(self):
        from academics.student_records import WithdrawalRequest
        with patch.dict(os.environ,{"FTBI_ALLOW_DEMO":"1","FTBI_BROWSER_TESTING":"1","FTBI_DEMO_PASSWORD":"synthetic-only-demo-password"}):
            call_command("seed_demo")
        reviewer=get_user_model().objects.get(username="demo-records-reviewer")
        self.assertTrue(reviewer.has_perms(["academics.change_withdrawalappeal","academics.change_enrollment","academics.add_finalgrade"]))
        self.assertFalse(reviewer.is_staff);self.assertFalse(reviewer.is_superuser)
        self.assertFalse(reviewer.has_perm("academics.view_studentprofile"))
        self.assertEqual(WithdrawalRequest.objects.filter(status="denied").count(),5)
        self.assertEqual(get_user_model().objects.count(),13)
