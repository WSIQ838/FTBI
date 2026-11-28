"""Disposable browser validation settings, never a deployment configuration."""
import os
from .settings import *  # noqa: F403
if os.environ.get("FTBI_BROWSER_TESTING") != "1":
    raise RuntimeError("Browser test settings require FTBI_BROWSER_TESTING=1")
DEBUG = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / ".browser-test.sqlite3"}}
SECURE_SSL_REDIRECT = SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
FTBI_REQUIRE_MFA = FTBI_REQUIRE_STAFF_MFA = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
FTBI_AI_ENABLED = FTBI_STRIPE_ENABLED = FTBI_OIDC_ENABLED = False

FTBI_PASSKEYS_ENABLED = True
FTBI_PASSKEY_RP_ID = "localhost"
FTBI_PASSKEY_ORIGIN = "http://localhost:8765"
