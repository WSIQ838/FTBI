from io import StringIO
from unittest.mock import patch
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from .account_security import AccountSecurity,AccountSession,AccountControlEvent
from .notification_models import DurableNotification,NotificationPreference,notify


class AccountSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user("student",password="a-long-test-password",email="student@example.invalid")
        self.other=get_user_model().objects.create_user("other")

    def test_revoked_session_is_denied_without_revoking_other_browser(self):
        first=Client(); second=Client()
        first.force_login(self.user); second.force_login(self.user)
        first.get(reverse("dashboard")); second.get(reverse("dashboard"))
        first_id=first.session["ftbi_session_id"]
        self.assertEqual(AccountSession.objects.count(),2)
        self.assertEqual(second.post(reverse("revoke_session",args=[first_id])).status_code,302)
        self.assertRedirects(first.get(reverse("dashboard")),reverse("login"),fetch_redirect_response=False)
        self.assertEqual(second.get(reverse("dashboard")).status_code,200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("revoke_session",args=[second.session["ftbi_session_id"]])).status_code,404)

    def test_account_admin_requires_permission_password_and_records_reason(self):
        self.client.force_login(self.user)
        url=reverse("account_control")
        self.assertEqual(self.client.get(url).status_code,403)
        admin=get_user_model().objects.create_user("security",is_staff=True,password="security-test-password")
        admin.user_permissions.add(Permission.objects.get(codename="change_accountsecurity"))
        self.client.force_login(admin)
        data={"user":self.user.pk,"action":"lock","reason":"Incident reference 123","password":"wrong"}
        self.assertContains(self.client.post(url,data),"Password confirmation failed")
        data["password"]="security-test-password"
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertTrue(AccountSecurity.objects.get(user=self.user).locked)
        self.assertEqual(AccountControlEvent.objects.get().reason,"Incident reference 123")
        self.assertEqual(Client().post(reverse("login"),{"username":"student","password":"a-long-test-password"}).status_code,429)

    def test_repeated_failed_login_and_password_change_notice(self):
        for i in range(10):
            self.client.post(reverse("login"),{"username":"student","password":"wrong"},REMOTE_ADDR=f"192.0.2.{i}")
        state=AccountSecurity.objects.get(user=self.user)
        self.assertGreater(state.locked_until,timezone.now())
        self.assertEqual(self.client.post(reverse("login"),{"username":"student","password":"a-long-test-password"}).status_code,429)
        self.user.set_password("another-long-test-password"); self.user.save()
        self.assertTrue(DurableNotification.objects.filter(user=self.user,subject="Your password changed").exists())

    def test_notification_history_and_preferences_are_private(self):
        notice=notify(self.user,"payment","Private update","Private body","unique-key")
        notify(self.user,"payment","Duplicate","Ignored","unique-key")
        self.assertEqual(DurableNotification.objects.count(),1)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("notification_history")),"Private body")
        self.assertEqual(self.client.post(reverse("read_notification",args=[notice.pk])).status_code,404)

    @override_settings(SMTP_CONFIGURED=True,EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_durable_delivery_deduplicates_and_honors_preference(self):
        notify(self.user,"payment","Private title","Sensitive body","delivery-key")
        call_command("deliver_notifications",stdout=StringIO())
        call_command("deliver_notifications",stdout=StringIO())
        self.assertEqual(len(mail.outbox),1)
        self.assertNotIn("Sensitive body",mail.outbox[0].body)
        NotificationPreference.objects.create(user=self.user,email_enabled=False)
        notice=notify(self.user,"admissions","Decision","Decision body","skip-key")
        call_command("deliver_notifications",stdout=StringIO()); notice.refresh_from_db()
        self.assertEqual(notice.email_status,"skipped")

    @override_settings(SMTP_CONFIGURED=True)
    @patch("academics.management.commands.deliver_notifications.send_mail",side_effect=OSError("temporary"))
    def test_delivery_failure_retains_retry_history(self,sender):
        notice=notify(self.user,"payment","Update","Body","failure-key")
        call_command("deliver_notifications",stdout=StringIO()); notice.refresh_from_db()
        self.assertEqual((notice.email_status,notice.email_attempts),("pending",1))
        self.assertGreater(notice.next_attempt,timezone.now())
