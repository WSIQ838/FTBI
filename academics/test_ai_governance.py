from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from .ai_governance import AIConfiguration,AIUsage,KnowledgeDocument,reserve_request,settle_request,retrieve_documents


@override_settings(FTBI_AI_ENABLED=True,FTBI_AI_MODEL="test-model")
class AIGovernanceTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user("learner")
        self.config=AIConfiguration.objects.create(pk=1,enabled=True,monthly_budget=1,input_price_per_million=1,output_price_per_million=2,policy_reference="Approved test policy")
        self.client.force_login(self.user)

    def test_private_and_unapproved_knowledge_is_not_retrieved(self):
        KnowledgeDocument.objects.create(title="Public policy",body="Attendance policy",audience="study",approved=True)
        KnowledgeDocument.objects.create(title="Staff policy",body="Attendance policy",audience="office",approved=True)
        KnowledgeDocument.objects.create(title="Draft policy",body="Attendance policy",audience="study",approved=False)
        self.assertEqual([d.title for d in retrieve_documents("study","attendance")],["Public policy"])
        usage,payload,docs=reserve_request(self.user,"study","attendance","Instructions")
        self.assertIn("Public policy",payload["input"])
        self.assertNotIn("Staff policy",payload["input"])
        self.assertNotIn("Draft policy",payload["input"])
        self.assertFalse(payload["store"])
        self.assertFalse(hasattr(usage,"question"))

    def test_quota_and_budget_block_before_provider(self):
        self.config.hourly_user_limit=1; self.config.save()
        reserve_request(self.user,"study","First","Instructions")
        with self.assertRaises(ValidationError): reserve_request(self.user,"study","Second","Instructions")
        self.config.hourly_user_limit=10; self.config.monthly_budget=Decimal("0.001"); self.config.save()
        with self.assertRaises(ValidationError): reserve_request(self.user,"study","Third","Instructions")
        self.assertEqual(AIUsage.objects.count(),1)

    def test_settlement_is_idempotent_and_anomaly_disables_provider(self):
        usage,_,_=reserve_request(self.user,"study","Question","Instructions")
        settle_request(usage,10,20); settle_request(usage,999999,999999)
        usage.refresh_from_db()
        self.assertEqual(usage.status,"succeeded")
        self.assertEqual(usage.charged_cost,Decimal("0.000050"))
        second,_,_=reserve_request(self.user,"study","Question","Instructions")
        settle_request(second,None,None)
        self.config.refresh_from_db(); self.assertFalse(self.config.enabled)
        second.refresh_from_db(); self.assertEqual(second.status,"anomaly")

    @patch("academics.assistant_views.ask_provider",side_effect=TimeoutError)
    def test_provider_failure_retains_reservation_and_no_prompt(self,provider):
        response=self.client.post(reverse("assistant"),{"mode":"study","question":"Explain a concept","consent":"on"})
        self.assertContains(response,"provider is unavailable")
        usage=AIUsage.objects.get()
        self.assertEqual(usage.status,"failed")
        self.assertEqual(usage.charged_cost,usage.reserved_cost)
        self.assertEqual(self.client.get(reverse("ai_configuration")).status_code,403)
        self.assertEqual(self.client.get(reverse("ai_usage")).status_code,403)

    @patch("academics.assistant_views.ask_provider")
    def test_missing_approval_blocks_requests(self,provider):
        self.config.enabled=False; self.config.save()
        response=self.client.post(reverse("assistant"),{"mode":"study","question":"Explain","consent":"on"})
        self.assertContains(response,"not approved or is disabled")
        provider.assert_not_called()
