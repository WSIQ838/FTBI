from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.db.models import Count,Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render,redirect
from django.utils import timezone
from django.conf import settings
from .ai_governance import AIConfiguration,AIUsage
from .operations import AuditEvent


@login_required
@permission_required("academics.change_aiconfiguration",raise_exception=True)
def configuration(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    class ConfigurationForm(forms.ModelForm):
        class Meta:
            model=AIConfiguration
            fields=["enabled","monthly_budget","input_price_per_million","output_price_per_million","hourly_user_limit","max_output_tokens","policy_reference"]
    config=AIConfiguration.objects.filter(pk=1).first() or AIConfiguration(pk=1)
    form=ConfigurationForm(request.POST if request.method=="POST" else None,instance=config)
    if request.method=="POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user,action="ai_configuration_updated",target="institution")
        return redirect("ai_configuration")
    return render(request,"ai_configuration.html",{"form":form,"provider_enabled":settings.FTBI_AI_ENABLED,"model":getattr(settings,"FTBI_AI_MODEL","Not configured")})


@login_required
@permission_required("academics.view_aiusage",raise_exception=True)
def usage(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    month=timezone.now().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    records=AIUsage.objects.filter(created__gte=month)
    return render(request,"ai_usage.html",{"rows":records.values("mode","status").annotate(requests=Count("pk"),cost=Sum("charged_cost"),input_tokens=Sum("input_tokens"),output_tokens=Sum("output_tokens")),"review":records.filter(status__in=["failed","anomaly"]).select_related("user").order_by("-created")[:100],"blocked":AuditEvent.objects.filter(action="ai_request_blocked",created__gte=month).count()})
