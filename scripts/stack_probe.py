"""Run only inside a disposable production-configured CI application container."""
import os
import sys
import json
from pathlib import Path
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","ftbi.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.core.cache import cache

if settings.DEBUG or connection.vendor!="postgresql": raise RuntimeError("Production database/settings not active")
if not settings.CACHES["default"]["BACKEND"].endswith("RedisCache"): raise RuntimeError("Redis backend not active")
cache.set("ftbi-ci-probe","ok",30)
if cache.get("ftbi-ci-probe")!="ok": raise RuntimeError("Redis probe failed")
request=Request("http://127.0.0.1:8000/health/ready/",headers={"Host":"localhost","X-Forwarded-Proto":"https"})
# The request is the fixed loopback readiness endpoint in the CI container.
with urlopen(request,timeout=10) as response:  # nosec B310
    if json.loads(response.read())["status"]!="ready": raise RuntimeError("Readiness failed")
print("Production-mode PostgreSQL, Redis and Gunicorn readiness passed; public TLS and institution acceptance not tested.")
