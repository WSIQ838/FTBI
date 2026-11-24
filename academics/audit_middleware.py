from .operations import AuditEvent

class MutationAuditMiddleware:
    def __init__(self,get_response):
        self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        user=getattr(request,"user",None)
        if user and user.is_authenticated and request.method in ("POST","PUT","PATCH","DELETE"):
            match=getattr(request,"resolver_match",None)
            name=(match.view_name if match else "unresolved") or "unnamed"
            AuditEvent.objects.create(actor=user,action=f"{request.method} {response.status_code}",target=name[:150])
        return response
