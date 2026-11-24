from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .operations import Message
class OperationsTests(TestCase):
    def test_messages_private(self):
        U=get_user_model()
        a=U.objects.create_user("a")
        b=U.objects.create_user("b")
        c=U.objects.create_user("c")
        m=Message.objects.create(sender=a,recipient=b,subject="Private subject",body="Private content")
        self.client.force_login(c)
        self.assertNotContains(self.client.get(reverse("inbox")),"Private subject")
        self.client.post(reverse("mark_read",args=[m.pk]))
        m.refresh_from_db()
        self.assertIsNone(m.read)
        self.assertEqual(self.client.get(reverse("reports")).status_code,403)
    def test_cannot_message_unrelated_user(self):
        U=get_user_model()
        a=U.objects.create_user("a")
        b=U.objects.create_user("b")
        self.client.force_login(a)
        self.client.post(reverse("inbox"),{"recipient":b.pk,"subject":"Test","body":"Test"})
        self.assertFalse(Message.objects.exists())
