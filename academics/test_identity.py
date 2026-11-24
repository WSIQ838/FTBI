from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from academics.identity_models import IdentityLink

class IdentityTests(TestCase):
    def test_subject_uniqueness_and_login_limit(self):
        cache.clear()
        user=get_user_model().objects.create_user("identity_student",password="example-test-password")
        IdentityLink.objects.create(user=user,subject="test-subject")
        self.assertEqual(user.institutional_identity.subject,"test-subject")
        for _ in range(10):
            self.assertEqual(self.client.post(reverse("login"),{"username":"identity_student","password":"wrong"}).status_code,200)
        self.assertEqual(self.client.post(reverse("login"),{"username":"identity_student","password":"wrong"}).status_code,429)
        cache.clear()
