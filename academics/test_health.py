from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
class HealthTests(TestCase):
    def test_health(self):
        self.assertEqual(self.client.get(reverse("health_live")).json(),{"status":"ok"})
        self.assertEqual(self.client.get(reverse("health_ready")).status_code,200)
    @patch("ftbi.health.cache.get",return_value=None)
    def test_cache_failure(self,_):
        self.assertEqual(self.client.get(reverse("health_ready")).status_code,503)
