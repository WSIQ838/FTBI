from django.test import TestCase,override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
import re
class ApplicantTests(TestCase):
    @override_settings(FTBI_PUBLIC_ADMISSIONS=False)
    def test_disabled(self):
        self.assertEqual(self.client.get(reverse("applicant_signup")).status_code,404)
    @override_settings(FTBI_PUBLIC_ADMISSIONS=True,SMTP_CONFIGURED=True,FTBI_ADMISSIONS_ORIGIN="https://college.example",EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unprivileged_account(self):
        cache.clear()
        response=self.client.post(reverse("applicant_signup"),{"username":"newapplicant","first_name":"Test","last_name":"Applicant","email":"applicant@example.invalid","password1":"long-test-passphrase-571","password2":"long-test-passphrase-571"})
        self.assertEqual(response.status_code,200)
        user=get_user_model().objects.get(username="newapplicant")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(hasattr(user,"student_profile"))
        # Exercise the delivered token; a newly generated token may cross a second boundary.
        match=re.search(r"https://college.example(/apply/activate/[^ ]+)",mail.outbox[0].body)
        self.assertIsNotNone(match)
        url=match.group(1)
        self.assertEqual(self.client.get(url).status_code,200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertRedirects(self.client.post(url),reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(self.client.post(url).status_code,404)
        cache.clear()
