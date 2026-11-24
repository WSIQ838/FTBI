from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

class WorkspaceTests(TestCase):
    def test_metrics_and_export_permission(self):
        user=get_user_model().objects.create_user("workspace_user")
        self.client.force_login(user)
        response=self.client.get(reverse("workspaces"))
        self.assertNotContains(response,"Net released ledger balance")
        self.assertEqual(self.client.get(reverse("institutional_csv")).status_code,403)
        for codename in ("view_studentprofile","view_enrollment","view_application"):
            user.user_permissions.add(Permission.objects.get(content_type__app_label="academics",codename=codename))
        self.assertContains(self.client.get(reverse("workspaces")),"Institutional leadership")
        result=self.client.get(reverse("institutional_csv"))
        self.assertContains(result,"Active enrollments")
        self.assertNotContains(result,user.username)
