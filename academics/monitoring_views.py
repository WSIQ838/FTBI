from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from ftbi.observability import collect_metrics
from .monitoring import OperationAlert

@login_required
@permission_required("academics.view_operationalert",raise_exception=True)
def operations(request):
    if not request.user.is_staff: raise PermissionDenied()
    response=render(request,"operations.html",{"payload":collect_metrics(),"alerts":OperationAlert.objects.exclude(code="monitor").order_by("code"),"heartbeat":OperationAlert.objects.filter(code="monitor").first()})
    response["Cache-Control"]="private, no-store"
    return response
