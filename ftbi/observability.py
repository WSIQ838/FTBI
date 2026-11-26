"""Operational signals without request bodies, credentials or student identifiers."""
import json
import logging
import os
import re
import secrets
import shutil
import time
from datetime import datetime,timezone as utc_timezone,timedelta
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse,Http404,HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

STARTED=time.monotonic()


class SafeJSONFormatter(logging.Formatter):
    def format(self,record):
        event=getattr(record,"event_code","log_event")
        if not isinstance(event,str) or not re.fullmatch(r"[a-z0-9_]{1,80}",event): event="log_event"
        data={"time":datetime.fromtimestamp(record.created,utc_timezone.utc).isoformat(),"level":record.levelname,"logger":record.name,"event":event}
        if isinstance(getattr(record,"status_code",None),int): data["status_code"]=record.status_code
        if record.exc_info and record.exc_info[0]: data["exception_type"]=record.exc_info[0].__name__
        # Deliberately omit arbitrary messages, exception values, arguments, URLs and request data.
        return json.dumps(data,sort_keys=True)


def backup_health():
    if not settings.FTBI_BACKUP_DIR: return {"state":"unconfigured","healthy":False}
    try:
        from scripts.backup_catalog import store
        root=store(settings.FTBI_BACKUP_DIR)
        path=root/".backup-status.json"
        if path.is_symlink() or path.stat().st_size>4096: raise ValueError()
        data=json.loads(path.read_text(encoding="utf-8"))
        last=datetime.fromisoformat(data["last_success"])
        age=(timezone.now()-last).total_seconds()
        healthy=data.get("result") in {"success","running"} and 0<=age<=settings.FTBI_BACKUP_MAX_AGE_HOURS*3600
        if data.get("result")=="running":
            run_age=(timezone.now()-datetime.fromisoformat(data["last_attempt"])).total_seconds()
            healthy=healthy and 0<=run_age<=3600
        return {"state":"healthy" if healthy else "stale_or_failed","healthy":healthy,"age_seconds":round(max(age,0))}
    except (OSError,ValueError,TypeError,KeyError): return {"state":"unavailable","healthy":False}


def collect_metrics():
    checks={};values={"worker_uptime_seconds":round(time.monotonic()-STARTED)}
    start=time.monotonic()
    try:
        with connection.cursor() as cursor: cursor.execute("SELECT 1")
        checks["database"]=True
        values["database_probe_ms"]=round((time.monotonic()-start)*1000,2)
    except Exception: checks["database"]=False
    key="operations-probe:"+secrets.token_hex(12)
    try:
        cache.set(key,1,15);checks["cache"]=cache.get(key)==1;cache.delete(key)
    except Exception: checks["cache"]=False
    try:
        disk=shutil.disk_usage(settings.BASE_DIR)
        values.update(disk_free_bytes=disk.free,disk_total_bytes=disk.total)
        checks["disk"]=disk.free>=settings.FTBI_MIN_DISK_FREE_MB*1024*1024
    except OSError: checks["disk"]=False
    if hasattr(os,"getloadavg"):
        try: values["load_average_1m"]=round(os.getloadavg()[0],2)
        except OSError: pass
    backup=backup_health();checks["backup"]=backup["healthy"];values["backup"]=backup
    if checks["database"]:
        from academics.notification_models import DurableNotification
        try:
            failed=DurableNotification.objects.filter(email_status="failed").count()
            delayed=DurableNotification.objects.filter(email_status="pending",created__lt=timezone.now()-timedelta(minutes=settings.FTBI_NOTIFICATION_MAX_WAIT_MINUTES)).count()
            values.update(failed_notifications=failed,delayed_notifications=delayed)
            checks["notifications"]=failed==0 and delayed==0
        except Exception: checks["notifications"]=False
    return {"healthy":all(checks.values()),"checked_at":timezone.now().isoformat(),"checks":checks,"metrics":values}


@require_safe
def metrics(request):
    token=settings.FTBI_MONITOR_TOKEN
    if not token: raise Http404()
    supplied=request.headers.get("Authorization","")
    if len(supplied)>2048 or not secrets.compare_digest(supplied.encode(),("Bearer "+token).encode()):
        return HttpResponse("Unauthorized",status=401)
    payload=collect_metrics()
    response=JsonResponse(payload,status=200 if payload["healthy"] else 503)
    response["Cache-Control"]="private, no-store"
    return response
