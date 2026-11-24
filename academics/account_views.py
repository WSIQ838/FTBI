from django import forms
from django.contrib.auth import get_user_model,logout
from django.contrib.auth.decorators import login_required,permission_required
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from .account_security import AccountSecurity,AccountSession,AccountControlEvent
from .notification_models import NotificationPreference,DurableNotification,notify
from .operations import AuditEvent


@login_required
def sessions(request):
    return render(request,"sessions.html",{"sessions":AccountSession.objects.filter(user=request.user,revoked=False,expires__gt=timezone.now()).order_by("-last_seen"),"current_id":getattr(request,"account_session",None).pk if getattr(request,"account_session",None) else None})


@login_required
@require_POST
def revoke_session(request,pk):
    session=get_object_or_404(AccountSession,pk=pk,user=request.user)
    session.revoked=True; session.save(update_fields=["revoked"])
    AuditEvent.objects.create(actor=request.user,action="session_revoked",target=str(pk))
    return redirect("account_sessions")


@login_required
@permission_required("academics.change_accountsecurity",raise_exception=True)
@sensitive_post_parameters("password")
def account_control(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    class ControlForm(forms.Form):
        user=forms.ModelChoiceField(queryset=get_user_model().objects.all())
        action=forms.ChoiceField(choices=[("revoke","Revoke all sessions"),("lock","Lock account and revoke sessions"),("unlock","Unlock account")])
        reason=forms.CharField(max_length=500,widget=forms.Textarea)
        password=forms.CharField(widget=forms.PasswordInput,strip=False,label="Confirm your password")
    form=ControlForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        target=form.cleaned_data["user"]
        if target.is_superuser and not request.user.is_superuser:
            form.add_error("user","Only a superuser can manage another superuser's security state.")
        elif not request.user.check_password(form.cleaned_data["password"]):
            form.add_error("password","Password confirmation failed.")
        else:
            with transaction.atomic():
                state,_=AccountSecurity.objects.get_or_create(user=target)
                state=AccountSecurity.objects.select_for_update().get(pk=state.pk)
                action=form.cleaned_data["action"]
                if action in ("lock","revoke"):
                    state.session_epoch+=1
                    AccountSession.objects.filter(user=target).update(revoked=True)
                if action=="lock": state.locked=True
                if action=="unlock": state.locked=False; state.locked_until=None; state.failures=0
                state.save()
                AccountControlEvent.objects.create(actor=request.user,target=target,action=action,reason=form.cleaned_data["reason"])
                event=AuditEvent.objects.create(actor=request.user,action="account_"+action,target=str(target.pk))
                notify(target,"security","Account security updated",f"The institution updated your account security ({action}). Contact support if you need assistance.",f"account-control:{event.pk}")
            return redirect("account_control")
    return render(request,"form.html",{"form":form,"heading":"Account security administration"})


@login_required
def preferences(request):
    class PreferenceForm(forms.ModelForm):
        class Meta:
            model=NotificationPreference
            fields=["email_enabled"]
    preference=NotificationPreference.objects.filter(user=request.user).first() or NotificationPreference(user=request.user)
    form=PreferenceForm(request.POST if request.method=="POST" else None,instance=preference)
    if request.method=="POST" and form.is_valid(): form.save(); return redirect("notification_history")
    return render(request,"form.html",{"form":form,"heading":"Notification preferences"})


@login_required
def notification_history(request):
    from django.core.paginator import Paginator
    page=Paginator(DurableNotification.objects.filter(user=request.user).order_by("-created"),50).get_page(request.GET.get("page"))
    return render(request,"notification_history.html",{"page":page})


@login_required
@require_POST
def read_notification(request,pk):
    notice=get_object_or_404(DurableNotification,pk=pk,user=request.user)
    if notice.read_at is None:
        notice.read_at=timezone.now(); notice.save(update_fields=["read_at"])
    return redirect("notification_history")
