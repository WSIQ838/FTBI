import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY")
    SECRET_KEY = "development-only-not-for-production"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "academics"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "ftbi.urls"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR / "templates"],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "ftbi.wsgi.application"
DATABASES = {"default": {"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR / "db.sqlite3"}}
if os.environ.get("POSTGRES_HOST"):
    DATABASES["default"] = {"ENGINE":"django.db.backends.postgresql","HOST":os.environ["POSTGRES_HOST"],"PORT":os.environ.get("POSTGRES_PORT","5432"),"NAME":os.environ["POSTGRES_DB"],"USER":os.environ["POSTGRES_USER"],"PASSWORD":os.environ["POSTGRES_PASSWORD"]}
AUTH_PASSWORD_VALIDATORS = [{"NAME":"django.contrib.auth.password_validation."+name} for name in ["UserAttributeSimilarityValidator","MinimumLengthValidator","CommonPasswordValidator","NumericPasswordValidator"]]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG

MIDDLEWARE.append('ftbi.security.PrivateResponseMiddleware')
MIDDLEWARE.insert(MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')+1,'ftbi.account_sessions.AccountSessionGate')
SECURE_CONTENT_TYPE_NOSNIFF = True

from urllib.parse import urlparse
FTBI_PAYMENT_URL = os.environ.get('FTBI_PAYMENT_URL','')
if FTBI_PAYMENT_URL and (urlparse(FTBI_PAYMENT_URL).scheme != 'https' or not urlparse(FTBI_PAYMENT_URL).hostname):
    raise RuntimeError('FTBI_PAYMENT_URL must be an HTTPS URL')

MIDDLEWARE.append('academics.audit_middleware.MutationAuditMiddleware')

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
if os.environ.get('DJANGO_TRUST_PROXY') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' if os.environ.get('SMTP_HOST') else 'django.core.mail.backends.locmem.EmailBackend'
EMAIL_HOST = os.environ.get('SMTP_HOST','localhost')
EMAIL_PORT = int(os.environ.get('SMTP_PORT','587'))
EMAIL_HOST_USER = os.environ.get('SMTP_USER','')
EMAIL_HOST_PASSWORD = os.environ.get('SMTP_PASSWORD','')
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get('SMTP_FROM','noreply@example.invalid')
PASSWORD_RESET_TIMEOUT = 3600

INSTALLED_APPS += ['django_otp','django_otp.plugins.otp_totp']
MIDDLEWARE += ['django_otp.middleware.OTPMiddleware','ftbi.mfa.MFAGate']
FTBI_REQUIRE_MFA = os.environ.get('FTBI_REQUIRE_MFA','0') == '1'
FTBI_REQUIRE_STAFF_MFA = os.environ.get('FTBI_REQUIRE_STAFF_MFA','0' if DEBUG else '1') == '1'

FTBI_OIDC_ENABLED = os.environ.get('FTBI_OIDC_ENABLED','0') == '1'
if FTBI_OIDC_ENABLED:
    INSTALLED_APPS.append('mozilla_django_oidc')
    AUTHENTICATION_BACKENDS = ['ftbi.identity.InstitutionalOIDCBackend','django.contrib.auth.backends.ModelBackend']
    OIDC_RP_CLIENT_ID = os.environ['OIDC_RP_CLIENT_ID']
    OIDC_RP_CLIENT_SECRET = os.environ['OIDC_RP_CLIENT_SECRET']
    OIDC_RP_SIGN_ALGO = 'RS256'
    OIDC_CREATE_USER = False
    OIDC_USE_NONCE = True
    OIDC_VERIFY_SSL = True
    OIDC_RP_SCOPES = 'openid'
    OIDC_STORE_ACCESS_TOKEN = False
    OIDC_STORE_ID_TOKEN = False
    for _name in ['OIDC_OP_AUTHORIZATION_ENDPOINT','OIDC_OP_TOKEN_ENDPOINT','OIDC_OP_USER_ENDPOINT','OIDC_OP_JWKS_ENDPOINT']:
        _value = os.environ[_name]
        if urlparse(_value).scheme != 'https' or not urlparse(_value).hostname:
            raise RuntimeError(_name+' must use HTTPS')
        globals()[_name] = _value

FTBI_INSTITUTION_NAME = os.environ.get('FTBI_INSTITUTION_NAME','FTBI Academic Portal')
FTBI_INSTITUTION_SHORT_NAME = os.environ.get('FTBI_INSTITUTION_SHORT_NAME','FTBI')
TEMPLATES[0]['OPTIONS']['context_processors'].append('ftbi.context.institution')

FTBI_PUBLIC_ADMISSIONS = os.environ.get('FTBI_PUBLIC_ADMISSIONS','0') == '1'

FTBI_STRIPE_ENABLED = os.environ.get('FTBI_STRIPE_ENABLED','0') == '1'
if FTBI_STRIPE_ENABLED:
    STRIPE_SECRET_KEY = os.environ['STRIPE_SECRET_KEY']
    STRIPE_WEBHOOK_SECRET = os.environ['STRIPE_WEBHOOK_SECRET']
    FTBI_PUBLIC_ORIGIN = os.environ['FTBI_PUBLIC_ORIGIN'].rstrip('/')
    _origin = urlparse(FTBI_PUBLIC_ORIGIN)
    if _origin.scheme != 'https' or not _origin.hostname or _origin.path or _origin.query or _origin.fragment or _origin.username or _origin.password:
        raise RuntimeError('FTBI_PUBLIC_ORIGIN must be an HTTPS origin')

FTBI_AI_ENABLED = os.environ.get('FTBI_AI_ENABLED','0') == '1'
if FTBI_AI_ENABLED:
    FTBI_AI_KEY = os.environ['FTBI_AI_KEY']
    FTBI_AI_MODEL = os.environ['FTBI_AI_MODEL']

SMTP_CONFIGURED = bool(os.environ.get('SMTP_HOST'))
FTBI_EMAIL_REMINDERS = os.environ.get('FTBI_EMAIL_REMINDERS','0') == '1'

FTBI_CLAMAV_HOST = os.environ.get('FTBI_CLAMAV_HOST','')
FTBI_CLAMAV_PORT = int(os.environ.get('FTBI_CLAMAV_PORT','3310'))

FTBI_REDIS_URL = os.environ.get('FTBI_REDIS_URL','')
if FTBI_REDIS_URL:
    CACHES = {'default':{'BACKEND':'django.core.cache.backends.redis.RedisCache','LOCATION':FTBI_REDIS_URL}}
SESSION_COOKIE_HTTPONLY = True

FTBI_ADMISSIONS_ORIGIN = os.environ.get('FTBI_ADMISSIONS_ORIGIN','').rstrip('/')
if FTBI_ADMISSIONS_ORIGIN:
    _admission_origin = urlparse(FTBI_ADMISSIONS_ORIGIN)
    if _admission_origin.scheme != 'https' or not _admission_origin.hostname or _admission_origin.path or _admission_origin.query or _admission_origin.fragment or _admission_origin.username or _admission_origin.password:
        raise RuntimeError('FTBI_ADMISSIONS_ORIGIN must be an HTTPS origin')

MIDDLEWARE.insert(MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')+1,'ftbi.preferences.PortalTimezoneMiddleware')

FTBI_CREDENTIAL_SIGNING_REQUIRED = os.environ.get('FTBI_CREDENTIAL_SIGNING_REQUIRED','0') == '1'
FTBI_SIGNING_P12_PATH = os.environ.get('FTBI_SIGNING_P12_PATH','')
FTBI_SIGNING_P12_PASSWORD = os.environ.get('FTBI_SIGNING_P12_PASSWORD','')

FTBI_MONITOR_TOKEN = os.environ.get('FTBI_MONITOR_TOKEN','')
if FTBI_MONITOR_TOKEN and len(FTBI_MONITOR_TOKEN)<32: raise RuntimeError('Monitoring token must contain at least 32 characters')
FTBI_BACKUP_DIR = os.environ.get('FTBI_BACKUP_DIR','')
FTBI_BACKUP_MAX_AGE_HOURS = int(os.environ.get('FTBI_BACKUP_MAX_AGE_HOURS','26'))
FTBI_MIN_DISK_FREE_MB = int(os.environ.get('FTBI_MIN_DISK_FREE_MB','1024'))
FTBI_NOTIFICATION_MAX_WAIT_MINUTES = int(os.environ.get('FTBI_NOTIFICATION_MAX_WAIT_MINUTES','60'))
if min(FTBI_BACKUP_MAX_AGE_HOURS,FTBI_MIN_DISK_FREE_MB,FTBI_NOTIFICATION_MAX_WAIT_MINUTES)<1: raise RuntimeError('Operational thresholds must be positive')
if os.environ.get('FTBI_JSON_LOGGING','0' if DEBUG else '1')=='1':
    LOGGING={'version':1,'disable_existing_loggers':False,'formatters':{'safe_json':{'()':'ftbi.observability.SafeJSONFormatter'}},'handlers':{'console':{'class':'logging.StreamHandler','formatter':'safe_json'}},'root':{'handlers':['console'],'level':'INFO'},'loggers':{'django':{'handlers':['console'],'level':'INFO','propagate':False}}}

FTBI_PASSKEYS_ENABLED = os.environ.get('FTBI_PASSKEYS_ENABLED','0') == '1'
FTBI_PASSKEY_RP_ID = os.environ.get('FTBI_PASSKEY_RP_ID','')
FTBI_PASSKEY_ORIGIN = os.environ.get('FTBI_PASSKEY_ORIGIN','')
