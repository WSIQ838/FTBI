from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django.utils import timezone
from academics.institution import PortalPreference

class PortalTimezoneMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        request.portal_preference=PortalPreference.objects.filter(user=request.user).first() if request.user.is_authenticated else None
        try:
            if request.portal_preference:
                try: timezone.activate(ZoneInfo(request.portal_preference.timezone))
                except (ZoneInfoNotFoundError,ValueError): timezone.deactivate()
            else: timezone.deactivate()
            return self.get_response(request)
        finally: timezone.deactivate()
