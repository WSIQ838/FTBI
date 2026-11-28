import hashlib
import json
import secrets
from datetime import timedelta
from unittest.mock import patch
import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
from webauthn.helpers import bytes_to_base64url,base64url_to_bytes
from .passkeys import PasskeyDevice,PasskeyChallenge,PasskeyIdentity
from .operations import AuditEvent
from .recovery_models import RecoveryCode

RP="portal.example.test"
ORIGIN="https://portal.example.test"
PASSWORD="synthetic-passkey-password"


class SyntheticAuthenticator:
    """Test-only software authenticator; server verification is the real library."""
    def __init__(self):
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.identifier=secrets.token_bytes(32)
    def response(self,options,register=False,origin=ORIGIN,rp=RP,verified=True,count=1,handle=None,cross_origin=False,eligible=False,backed_up=False):
        client=json.dumps({"type":"webauthn.create" if register else "webauthn.get","challenge":options["challenge"],"origin":origin,"crossOrigin":cross_origin}).encode()
        flags=1+(4 if verified else 0)+(64 if register else 0)+(8 if eligible else 0)+(16 if backed_up else 0)
        data=hashlib.sha256(rp.encode()).digest()+bytes([flags])+(0 if register else count).to_bytes(4,"big")
        response={"clientDataJSON":bytes_to_base64url(client)}
        if register:
            numbers=self.key.public_key().public_numbers()
            public=cbor2.dumps({1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,"big"),-3:numbers.y.to_bytes(32,"big")})
            data+=bytes(16)+len(self.identifier).to_bytes(2,"big")+self.identifier+public
            response["attestationObject"]=bytes_to_base64url(cbor2.dumps({"fmt":"none","attStmt":{},"authData":data}))
        else:
            response.update(authenticatorData=bytes_to_base64url(data),signature=bytes_to_base64url(self.key.sign(data+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))),userHandle=handle)
        identifier=bytes_to_base64url(self.identifier)
        return {"id":identifier,"rawId":identifier,"type":"public-key","response":response}


@override_settings(DEBUG=True,FTBI_PASSKEYS_ENABLED=True,FTBI_PASSKEY_RP_ID=RP,FTBI_PASSKEY_ORIGIN=ORIGIN)
class PasskeyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user("passkey-user",password=PASSWORD)
        self.client.force_login(self.user)
        self.authenticator=SyntheticAuthenticator()
    def begin(self,purpose="register",client=None):
        return (client or self.client).post(reverse("passkey_begin",args=[purpose]),{"label":"Synthetic key","password":PASSWORD})
    def finish(self,purpose,payload,client=None):
        return (client or self.client).post(reverse("passkey_finish",args=[purpose]),data=json.dumps(payload),content_type="application/json")
    def register(self):
        response=self.begin();self.assertEqual(response.status_code,200)
        payload=self.authenticator.response(response.json(),register=True)
        self.assertEqual(self.finish("register",payload).status_code,200)
        return payload
    def unverify(self):
        self.client.logout();self.client.force_login(self.user)

    def test_real_signed_authentication_replay_and_revocation(self):
        self.register();device=PasskeyDevice.objects.get()
        self.unverify();self.assertEqual(self.client.get(reverse("dashboard")).status_code,302)
        options=self.begin("authenticate").json()
        payload=self.authenticator.response(options,handle=bytes_to_base64url(bytes(PasskeyIdentity.objects.get(user=self.user).handle)))
        self.assertEqual(self.finish("authenticate",payload).status_code,200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code,200)
        device.refresh_from_db();self.assertEqual(device.sign_count,1)
        self.assertEqual(self.finish("authenticate",payload).status_code,400)
        self.assertEqual(self.client.post(reverse("passkey_revoke",args=[device.pk]),{"password":"wrong"}).status_code,403)
        self.assertEqual(self.client.post(reverse("passkey_revoke",args=[device.pk]),{"password":PASSWORD}).status_code,302)
        device.refresh_from_db();self.assertFalse(device.confirmed)
        self.assertIsNotNone(device.revoked_at)
        self.assertEqual(self.client.post(reverse("recovery_codes"),{"password":PASSWORD}).status_code,403)

    def test_registration_requires_password_existing_mfa_and_user_verification(self):
        self.assertEqual(self.client.post(reverse("passkey_begin",args=["register"]),{"label":"Key","password":"wrong"}).status_code,403)
        options=self.begin().json()
        self.assertEqual(self.finish("register",self.authenticator.response(options,register=True,verified=False)).status_code,400)
        self.assertFalse(PasskeyDevice.objects.exists())
        self.register();self.unverify()
        self.assertEqual(self.begin().status_code,403)
        self.assertEqual(self.client.get(reverse("passkey_manage")).status_code,302)

    def test_wrong_origin_rp_challenge_and_signature_are_rejected(self):
        self.register();self.unverify()
        for change in [{"origin":"https://evil.example"},{"rp":"evil.example"},{"verified":False},{"cross_origin":True},{"eligible":True,"backed_up":True}]:
            payload=self.authenticator.response(self.begin("authenticate").json(),**change)
            self.assertEqual(self.finish("authenticate",payload).status_code,400)
        options=self.begin("authenticate").json();options["challenge"]=bytes_to_base64url(b"wrong challenge")
        self.assertEqual(self.finish("authenticate",self.authenticator.response(options)).status_code,400)
        payload=self.authenticator.response(self.begin("authenticate").json());payload["response"]["signature"]=bytes_to_base64url(b"not a signature")
        self.assertEqual(self.finish("authenticate",payload).status_code,400)
        self.assertFalse(AuditEvent.objects.filter(action="passkey_verified").exists())

    def test_ceremony_is_session_bound_expiring_and_policy_bound(self):
        options=self.begin().json();payload=self.authenticator.response(options,register=True)
        other=Client();other.force_login(self.user)
        self.assertEqual(self.finish("register",payload,other).status_code,400)
        PasskeyChallenge.objects.filter(user=self.user).update(expires=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.finish("register",payload).status_code,400)
        options=self.begin().json();payload=self.authenticator.response(options,register=True)
        with override_settings(FTBI_PASSKEY_ORIGIN="https://portal.example.test:8443"):
            self.assertEqual(self.finish("register",payload).status_code,400)
        self.assertFalse(PasskeyDevice.objects.exists())

    def test_user_handle_and_credential_ownership_are_enforced(self):
        self.register();self.unverify()
        payload=self.authenticator.response(self.begin("authenticate").json(),handle=bytes_to_base64url(b"another user"))
        self.assertEqual(self.finish("authenticate",payload).status_code,400)
        payload=self.authenticator.response(self.begin("authenticate").json());payload["id"]=bytes_to_base64url(secrets.token_bytes(32))
        self.assertEqual(self.finish("authenticate",payload).status_code,400)
        other=get_user_model().objects.create_user("other-passkey-user",password=PASSWORD)
        self.client.force_login(other)
        otp=TOTPDevice.objects.create(user=other,confirmed=True)
        session=self.client.session;session[DEVICE_ID_SESSION_KEY]=otp.persistent_id;session.save()
        self.assertEqual(self.client.post(reverse("passkey_revoke",args=[PasskeyDevice.objects.get().pk]),{"password":PASSWORD}).status_code,404)

    def test_counter_rollback_rejected_and_notification_failure_is_atomic(self):
        options=self.begin().json();payload=self.authenticator.response(options,register=True)
        with patch("ftbi.passkeys.notify",side_effect=ValueError("Synthetic queue failure")):
            with self.assertRaises(ValueError): self.finish("register",payload)
        self.assertFalse(PasskeyDevice.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="passkey_registered").exists())
        self.register();self.unverify()
        payload=self.authenticator.response(self.begin("authenticate").json(),count=3)
        self.assertEqual(self.finish("authenticate",payload).status_code,200)
        self.unverify();payload=self.authenticator.response(self.begin("authenticate").json(),count=2)
        self.assertEqual(self.finish("authenticate",payload).status_code,400)

    def test_csrf_limits_disabled_configuration_and_malformed_payload(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(self.begin(client=client).status_code,403)
        with override_settings(FTBI_PASSKEYS_ENABLED=False): self.assertEqual(self.begin().status_code,503)
        with override_settings(DEBUG=False,FTBI_PASSKEY_ORIGIN="http://portal.example.test"): self.assertEqual(self.begin().status_code,503)
        self.assertEqual(self.client.post(reverse("passkey_finish",args=["register"]),data="[",content_type="application/json").status_code,400)
        self.assertEqual(self.client.post(reverse("passkey_finish",args=["register"]),data="x"*32769,content_type="application/json").status_code,413)
        cache.set(f"passkey-ceremony:{self.user.pk}",30,300)
        self.assertEqual(self.begin().status_code,429)

    def test_passkey_only_account_can_use_existing_single_use_recovery_flow(self):
        self.register()
        response=self.client.post(reverse("recovery_codes"),{"password":PASSWORD})
        code=response.context["codes"][0]
        self.unverify()
        self.assertEqual(self.client.post(reverse("mfa_recover"),{"code":code}).status_code,302)
        self.assertEqual(RecoveryCode.objects.filter(user=self.user).count(),7)
        self.unverify()
        self.assertContains(self.client.post(reverse("mfa_recover"),{"code":code}),"Invalid or already used")

    def test_configuration_and_device_limits_fail_closed(self):
        from ftbi.passkey_checks import passkey_configuration_check
        for origin in ["https://portal.example.test/","https://portal.example.test:443","http://portal.example.test"]:
            with override_settings(FTBI_PASSKEY_ORIGIN=origin):
                self.assertEqual(self.begin().status_code,503)
                self.assertEqual(passkey_configuration_check(None)[0].id,"ftbi.E001")
        self.register()
        for index in range(7):
            PasskeyDevice.objects.create(user=self.user,name=f"Synthetic {index}",credential_id=f"synthetic-{index}",public_key=b"unused")
        self.assertEqual(self.begin().status_code,400)
        self.unverify()
        with override_settings(FTBI_PASSKEYS_ENABLED=False):
            self.assertEqual(self.client.get(reverse("dashboard")).status_code,302)
            self.assertEqual(self.client.get(reverse("passkey_verify")).status_code,503)
