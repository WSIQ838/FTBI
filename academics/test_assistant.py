from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache

class AssistantTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("assistant_student"))
        cache.clear()
    @override_settings(FTBI_AI_ENABLED=False)
    def test_disabled(self):
        self.assertEqual(self.client.get(reverse("assistant")).status_code,404)
    @override_settings(FTBI_AI_ENABLED=True)
    @patch("academics.assistant_views.ask_provider",return_value="Study guidance")
    def test_scope_and_consent(self,provider):
        url=reverse("assistant")
        self.client.post(url,{"mode":"office","question":"Hello","consent":"on"})
        self.client.post(url,{"mode":"study","question":"Hello"})
        provider.assert_not_called()
        response=self.client.post(url,{"mode":"study","question":"Explain gravity","consent":"on"})
        self.assertContains(response,"Study guidance")
        provider.assert_called_once_with("study","Explain gravity")
