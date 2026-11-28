"""Real SMTP/STARTTLS acceptance against an isolated, non-relaying Mailpit fixture."""
import json
import os
from io import StringIO
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler


def require(condition,message):
    if not condition: raise RuntimeError(message)


def validate(config,environ):
    require(environ.get("FTBI_SMTP_TESTING")=="1" and config.DEBUG,"Explicit disposable SMTP opt-in required")
    require(config.EMAIL_BACKEND=="django.core.mail.backends.smtp.EmailBackend" and config.SMTP_CONFIGURED,"Real SMTP backend required")
    require(config.EMAIL_HOST=="127.0.0.1" and config.EMAIL_PORT==1025,"Only the fixed loopback SMTP fixture is permitted")
    require(config.EMAIL_USE_TLS and not config.EMAIL_USE_SSL,"Verified STARTTLS is required")
    require(config.EMAIL_HOST_USER=="smtp-fixture" and config.EMAIL_HOST_PASSWORD=="synthetic-smtp-password","Only synthetic SMTP credentials are permitted")
    require(config.DEFAULT_FROM_EMAIL=="portal@example.invalid","Only the synthetic sender is permitted")
    require(environ.get("SSL_CERT_FILE") and environ.get("FTBI_SMTP_UNTRUSTED_CA"),"Disposable TLS certificates required")
    require(environ["SSL_CERT_FILE"]!=environ["FTBI_SMTP_UNTRUSTED_CA"],"Distinct trusted and untrusted certificates required")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError("Mail capture redirects are forbidden")


def capture(path):
    require(path in {"/api/v1/messages","/api/v1/message/latest"},"Unexpected capture path")
    opener=build_opener(ProxyHandler({}),NoRedirects())
    # Fixed numeric loopback, fixed read paths, no proxies or redirects.
    with opener.open("http://127.0.0.1:8025"+path,timeout=3) as response:  # nosec B310
        content=response.read(1024*1024+1)
    require(len(content)<=1024*1024,"Capture response exceeded its limit")
    return json.loads(content)


def count(): return capture("/api/v1/messages")["total"]


def check_delivery(expected):
    require(count()==expected,"Unexpected captured message count")
    message=capture("/api/v1/message/latest")
    require(message["Subject"]=="FTBI account notification","Unexpected notification subject")
    require(message["From"]["Address"]=="portal@example.invalid","Unexpected sender")
    require([row["Address"] for row in message["To"]]==["student@example.invalid"],"Unexpected recipient")
    require("new update in your FTBI account" in message["Text"],"Missing generic portal notice")
    require("PRIVATE-SYNTHETIC" not in json.dumps(message),"Private portal content escaped into email")
    require(not message.get("Attachments"),"Unexpected email attachment")


def run():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","ftbi.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import override_settings
    from django.utils import timezone
    from academics.notification_models import notify,NotificationPreference,DurableNotification
    validate(settings,os.environ)
    require(settings.DATABASES["default"]["ENGINE"]=="django.db.backends.sqlite3","Disposable SQLite database required")
    require(not get_user_model().objects.exists(),"An empty user database is required")
    require(not any(model.objects.exists() for model in apps.get_app_config("academics").get_models()),"An empty application database is required")
    for attempt in range(30):
        try:
            initial=count();break
        except (URLError,OSError):
            if attempt==29: raise
            time.sleep(.5)
    require(initial==0,"An empty capture mailbox is required")
    user=get_user_model().objects.create_user("smtp-fixture",email="student@example.invalid")
    opted_out=get_user_model().objects.create_user("smtp-optout",email="optout@example.invalid")
    NotificationPreference.objects.create(user=opted_out,email_enabled=False)
    def notice(key,recipient=user):
        return notify(recipient,"security","PRIVATE-SYNTHETIC-SUBJECT","PRIVATE-SYNTHETIC-RECORD-CONTENT",key)
    def deliver(): call_command("deliver_notifications",limit=20,stdout=StringIO())
    def state(record,status,attempts):
        record.refresh_from_db()
        require(record.email_status==status and record.email_attempts==attempts,"Unexpected durable notification state")
    def eligible(record):
        DurableNotification.objects.filter(pk=record.pk).update(next_attempt=timezone.now())
    first=notice("smtp-success");skipped=notice("smtp-optout",opted_out)
    deliver();state(first,"sent",1);state(skipped,"skipped",0);check_delivery(1)
    deliver();check_delivery(1)
    auth=notice("smtp-auth-failure")
    with override_settings(EMAIL_HOST_PASSWORD="deliberately-wrong-synthetic-password"): deliver()
    state(auth,"pending",1);require(count()==1,"Authentication failure delivered a message")
    require(auth.next_attempt>timezone.now(),"Authentication failure did not defer retry")
    deliver();state(auth,"pending",1);require(count()==1,"Retry backoff was bypassed")
    eligible(auth);deliver();state(auth,"sent",2);check_delivery(2)
    tls=notice("smtp-untrusted-certificate")
    with patch.dict(os.environ,{"SSL_CERT_FILE":os.environ["FTBI_SMTP_UNTRUSTED_CA"]}): deliver()
    state(tls,"pending",1);require(count()==2,"Untrusted TLS certificate was accepted")
    eligible(tls);deliver();state(tls,"sent",2);check_delivery(3)
    unavailable=notice("smtp-unavailable")
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as blocked:
        blocked.bind(("127.0.0.1",0))  # Bound but not listening: no other service can receive this attempt.
        with override_settings(EMAIL_PORT=blocked.getsockname()[1],EMAIL_TIMEOUT=2): deliver()
    state(unavailable,"pending",1);require(count()==3,"Unavailable SMTP reported delivery")
    eligible(unavailable);deliver();state(unavailable,"sent",2);check_delivery(4)
    exhausted=notice("smtp-exhausted")
    for attempt in range(5):
        eligible(exhausted)
        with override_settings(EMAIL_HOST_PASSWORD="deliberately-wrong-synthetic-password"): deliver()
    state(exhausted,"failed",5);require(count()==4,"Failed credentials delivered a message")
    deliver();state(exhausted,"failed",5);require(count()==4,"Terminal failure retried automatically")
    return {"format":"ftbi-smtp-validation-v1","accepted":True,"captured_messages":4,
            "checks":["authenticated_starttls","generic_content","recipient_privacy","opt_out","repeat_safe",
                      "auth_failure","retry_backoff","certificate_rejection","connection_failure","retry_recovery","terminal_failure"],
            "scope":"Disposable loopback capture only; no external recipients or institutional SMTP acceptance."}


if __name__=="__main__":
    try: report=run()
    except Exception as error:
        report={"format":"ftbi-smtp-validation-v1","accepted":False,"failure_type":type(error).__name__}
        print("SMTP fixture validation failed:",type(error).__name__,file=sys.stderr)
    Path("smtp-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    raise SystemExit(0 if report["accepted"] else 1)
