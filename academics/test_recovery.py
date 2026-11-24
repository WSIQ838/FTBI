from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice
from .recovery_models import RecoveryCode
class RecoveryTests(TestCase):
    def test_single_use(self):
        user=get_user_model().objects.create_user("recover_user")
        TOTPDevice.objects.create(user=user,name="Authenticator",confirmed=True)
        code="a"*24
        RecoveryCode.objects.create(user=user,digest=make_password(code))
        self.client.force_login(user)
        url=reverse("mfa_recover")
        self.assertEqual(self.client.post(url,{"code":code}).status_code,302)
        self.assertFalse(RecoveryCode.objects.filter(user=user).exists())
        self.client.logout()
        self.client.force_login(user)
        self.assertContains(self.client.post(url,{"code":code}),"Invalid or already used")
