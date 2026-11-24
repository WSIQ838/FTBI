from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.views.decorators.http import require_safe
@require_safe
def live(request):
    return JsonResponse({"status":"ok"})
@require_safe
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.set("ftbi-readiness",1,15)
        if cache.get("ftbi-readiness")!=1:
            raise RuntimeError()
    except Exception:
        return JsonResponse({"status":"unavailable"},status=503)
    return JsonResponse({"status":"ready"})
