from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from scripts import smtp_probe as probe


class SMTPProbeTests(SimpleTestCase):
    def test_fixture_guards(self):
        values=dict(DEBUG=True, EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                    SMTP_CONFIGURED=True, EMAIL_HOST="127.0.0.1", EMAIL_PORT=1025,
                    EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_HOST_USER="smtp-fixture",
                    EMAIL_HOST_PASSWORD="synthetic-smtp-password", DEFAULT_FROM_EMAIL="portal@example.invalid")
        env=dict(FTBI_SMTP_TESTING="1", SSL_CERT_FILE="trusted.pem", FTBI_SMTP_UNTRUSTED_CA="other.pem")
        probe.validate(SimpleNamespace(**values),env)
        for key,value in dict(DEBUG=False,EMAIL_HOST="mail.example.com",EMAIL_PORT=587,
                              EMAIL_USE_TLS=False,EMAIL_USE_SSL=True,SMTP_CONFIGURED=False,
                              EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
                              EMAIL_HOST_USER="real",EMAIL_HOST_PASSWORD="real",DEFAULT_FROM_EMAIL="real@example.com").items():
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                probe.validate(SimpleNamespace(**(values|{key:value})),env)
        for changes in ({"FTBI_SMTP_TESTING":"0"},{"SSL_CERT_FILE":""},{"FTBI_SMTP_UNTRUSTED_CA":"trusted.pem"}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                probe.validate(SimpleNamespace(**values),env|changes)

    def test_capture_rejects_arbitrary_paths_and_redirects(self):
        with patch.object(probe,"build_opener") as opener:
            for path in ("https://example.com", "//example.com", "/api/v1/messages?limit=100", "/"):
                with self.assertRaises(RuntimeError): probe.capture(path)
            opener.assert_not_called()
        with self.assertRaises(ValueError): probe.NoRedirects().redirect_request(None,None,None,None,None,None)

    def test_delivery_asserts_privacy_and_envelope(self):
        clean={"Subject":"FTBI account notification","From":{"Address":"portal@example.invalid"},
               "To":[{"Address":"student@example.invalid"}],"Text":"There is a new update in your FTBI account.","Attachments":[]}
        with patch.object(probe,"count",return_value=1),patch.object(probe,"capture",return_value=clean):
            probe.check_delivery(1)
        for changes in ({"Text":"PRIVATE-SYNTHETIC"},{"Subject":"Private grade"},
                        {"To":[{"Address":"other@example.invalid"}]},{"Attachments":[{"Name":"record.pdf"}]},
                        {"HTML":"PRIVATE-SYNTHETIC"}):
            with self.subTest(changes=changes),patch.object(probe,"count",return_value=1),patch.object(probe,"capture",return_value=clean|changes),self.assertRaises(RuntimeError):
                probe.check_delivery(1)
