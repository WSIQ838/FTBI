from django.contrib.auth.signals import user_logged_in,user_logged_out
from django.dispatch import receiver
from .operations import AuditEvent

@receiver(user_logged_in,dispatch_uid="ftbi_login_audit")
def log_login(sender,request,user,**kwargs):
    AuditEvent.objects.create(actor=user,action="login",target="account")

@receiver(user_logged_out,dispatch_uid="ftbi_logout_audit")
def log_logout(sender,request,user,**kwargs):
    if user is not None:
        AuditEvent.objects.create(actor=user,action="logout",target="account")
