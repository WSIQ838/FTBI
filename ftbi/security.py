from django.utils.cache import add_never_cache_headers
from django.conf import settings

class PrivateResponseMiddleware:
    def __init__(self,get_response):
        self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        if getattr(request,"user",None) and request.user.is_authenticated:
            add_never_cache_headers(response)
        response.headers.setdefault("Referrer-Policy","same-origin")
        response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        return response
