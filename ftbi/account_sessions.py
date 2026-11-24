from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from academics.account_security import AccountSecurity,AccountSession


class AccountSessionGate:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        if request.user.is_authenticated:
            state,_=AccountSecurity.objects.get_or_create(user=request.user)
            session_id=request.session.get("ftbi_session_id")
            session=AccountSession.objects.filter(pk=session_id,user=request.user).first() if session_id else None
            invalid=(state.locked or request.session.get("ftbi_session_epoch",0)!=state.session_epoch or (session_id and (session is None or session.revoked)))
            if invalid:
                logout(request)
                return redirect("login")
            now=timezone.now()
            if session is None:
                session=AccountSession.objects.create(user=request.user,label=request.META.get("HTTP_USER_AGENT","Unknown browser")[:200],last_seen=now,expires=request.session.get_expiry_date())
                request.session["ftbi_session_id"]=session.pk
            elif (now-session.last_seen).total_seconds()>60:
                AccountSession.objects.filter(pk=session.pk).update(last_seen=now,expires=request.session.get_expiry_date())
            request.account_session=session
        return self.get_response(request)
