from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse
import hashlib

class LimitedLoginView(LoginView):
    def post(self,request,*args,**kwargs):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from academics.account_security import AccountSecurity
        user=get_user_model().objects.filter(username=request.POST.get("username","")).first()
        state=AccountSecurity.objects.filter(user=user).first() if user else None
        if state and (state.locked or (state.locked_until and state.locked_until>timezone.now())):
            return HttpResponse("Sign-in is temporarily unavailable. Try later or contact account support.",status=429)
        # Do not trust client-supplied forwarded IP headers.
        ip=request.META.get("REMOTE_ADDR","unknown")
        username=request.POST.get("username","").strip().casefold()[:254]
        key="login:"+hashlib.sha256((ip+"|"+username).encode()).hexdigest()
        cache.add(key,0,timeout=300)
        try:
            count=cache.incr(key)
        except ValueError:
            cache.add(key,1,timeout=300)
            count=1
        if count>10:
            return HttpResponse("Too many sign-in attempts. Try again later.",status=429)
        response=super().post(request,*args,**kwargs)
        if request.user.is_authenticated:
            cache.delete(key)
        return response
