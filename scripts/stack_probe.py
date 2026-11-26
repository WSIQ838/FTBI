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

from urllib.error import HTTPError
endpoint="http://127.0.0.1:8000/health/metrics/"
headers={"Host":"localhost","X-Forwarded-Proto":"https"}
try:
    urlopen(Request(endpoint,headers=headers),timeout=10)  # nosec B310
    raise RuntimeError("Metrics accepted an unauthenticated request")
except HTTPError as error:
    if error.code!=401: raise
headers["Authorization"]="Bearer "+settings.FTBI_MONITOR_TOKEN
try:
    response=urlopen(Request(endpoint,headers=headers),timeout=10)  # nosec B310
except HTTPError as error:
    if error.code!=503: raise
    response=error
with response:
    payload=json.loads(response.read())
    if not payload["checks"]["database"] or not payload["checks"]["cache"]: raise RuntimeError("Operational dependency checks failed")
    if payload["metrics"]["backup"]["state"]!="unconfigured": raise RuntimeError("CI must not claim an institutional backup store is configured")
print("Private operational metrics verified; missing institutional backup configuration correctly remains unhealthy.")
