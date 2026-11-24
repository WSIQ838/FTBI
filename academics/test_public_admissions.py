from django.test import TestCase,override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache
class ApplicantTests(TestCase):
    @override_settings(FTBI_PUBLIC_ADMISSIONS=False)
    def test_disabled(self):
        self.assertEqual(self.client.get(reverse("applicant_signup")).status_code,404)
    @override_settings(FTBI_PUBLIC_ADMISSIONS=True)
    def test_unprivileged_account(self):
        cache.clear()
        response=self.client.post(reverse("applicant_signup"),{"username":"newapplicant","first_name":"Test","last_name":"Applicant","password1":"long-test-passphrase-571","password2":"long-test-passphrase-571"})
        self.assertRedirects(response,reverse("login"))
        user=get_user_model().objects.get(username="newapplicant")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(hasattr(user,"student_profile"))
        cache.clear()
