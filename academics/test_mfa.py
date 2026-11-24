from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

class MFATests(TestCase):
    @override_settings(FTBI_REQUIRE_MFA=True)
    def test_required_gate(self):
        user=get_user_model().objects.create_user("mfa_student",password="test-password")
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("dashboard")),reverse("mfa_setup"))
        self.client.post(reverse("mfa_setup"),{"action":"start","password":"wrong"})
        self.assertFalse(TOTPDevice.objects.filter(user=user).exists())
        self.client.post(reverse("mfa_setup"),{"action":"start","password":"test-password"})
        self.assertTrue(TOTPDevice.objects.filter(user=user,confirmed=False).exists())
        self.assertRedirects(self.client.get(reverse("dashboard")),reverse("mfa_setup"))
    def test_enrolled_user_cannot_skip(self):
        user=get_user_model().objects.create_user("enrolled")
        TOTPDevice.objects.create(user=user,name="test",confirmed=True)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("dashboard")),reverse("mfa_verify"))
        self.assertEqual(self.client.post(reverse("mfa_verify"),{"token":"invalid"}).status_code,200)
