import hashlib
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in,user_login_failed
from django.db.models.signals import pre_save,post_save
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from .account_security import AccountSecurity,SecurityIncident
from .notification_models import notify
from .operations import AuditEvent
from .services import FinalGrade
from .registrar import StudentProfile
from .student_records import StudentStatusRecord


@receiver(user_login_failed,dispatch_uid="ftbi_failed_login_state")
def failed_login(sender,credentials,request,**kwargs):
    user=get_user_model().objects.filter(username=credentials.get("username","")).first()
    if user is None: return
    with transaction.atomic():
        state,_=AccountSecurity.objects.get_or_create(user=user)
        state=AccountSecurity.objects.select_for_update().get(pk=state.pk)
        now=timezone.now()
        state.failures=state.failures+1 if state.last_failure and now-state.last_failure<timedelta(minutes=15) else 1
        state.last_failure=now
        if state.failures>=10:
            state.locked_until=now+timedelta(minutes=15)
            notify(user,"security","Sign-in attempts temporarily blocked","Repeated failed sign-ins triggered a temporary lock. Review your account security.",f"login-lock:{user.pk}:{now.strftime('%Y%m%d%H%M')}")
        state.save()
    AuditEvent.objects.create(actor=user,action="login_failed",target="account")


@receiver(user_logged_in,dispatch_uid="ftbi_login_security_state")
def login_state(sender,request,user,**kwargs):
    state,_=AccountSecurity.objects.get_or_create(user=user)
    request.session["ftbi_session_epoch"]=state.session_epoch
    request.session.pop("ftbi_session_id",None)
    network=hashlib.sha256(request.META.get("REMOTE_ADDR","unknown").encode()).hexdigest()
    if state.last_network and state.last_network!=network:
        notify(user,"security","Sign-in from a different network","A sign-in used a different network address. If it was not yours, revoke your sessions and change your password.",f"new-network:{user.pk}:{network}:{timezone.localdate()}")
    state.last_network=network; state.failures=0; state.locked_until=None
    state.save(update_fields=["last_network","failures","locked_until"])


@receiver(pre_save,sender=get_user_model(),dispatch_uid="ftbi_password_change_detect")
def password_before(sender,instance,**kwargs):
    if instance.pk:
        old=sender.objects.filter(pk=instance.pk).values_list("password",flat=True).first()
        instance._password_changed=bool(old and old!=instance.password)


@receiver(post_save,sender=get_user_model(),dispatch_uid="ftbi_password_change_notice")
def password_after(sender,instance,**kwargs):
    if getattr(instance,"_password_changed",False):
        import uuid
        notify(instance,"security","Your password changed","Your account password changed. If this was unexpected, contact the institution's security team.",f"password-change:{instance.pk}:{uuid.uuid4()}")
        instance._password_changed=False


@receiver(post_save,sender=SecurityIncident,dispatch_uid="ftbi_incident_notice")
def incident_notice(sender,instance,created,**kwargs):
    notify(instance.owner,"security","Security incident assigned or updated",f"Review incident #{instance.pk}: {instance.status}.",f"incident:{instance.pk}:{instance.updated.isoformat()}")


@receiver(post_save,sender=FinalGrade,dispatch_uid="ftbi_final_grade_notice")
def grade_released(sender,instance,**kwargs):
    if instance.released:
        notify(instance.student.user,"grades","Final grade available","A released final grade is available in your academic record.",f"final-grade:{instance.pk}:{instance.letter}:{instance.quality_points}:{instance.credits_earned}")


@receiver(pre_save,sender=StudentProfile,dispatch_uid="ftbi_student_status_before")
def student_status_before(sender,instance,**kwargs):
    instance._previous_status=sender.objects.filter(pk=instance.pk).values_list("status",flat=True).first() if instance.pk else None


@receiver(post_save,sender=StudentProfile,dispatch_uid="ftbi_student_status_after")
def student_status_after(sender,instance,created,**kwargs):
    previous=getattr(instance,"_previous_status",None)
    if created or previous!=instance.status:
        StudentStatusRecord.objects.create(student=instance,previous=previous or "",current=instance.status,actor=getattr(instance,"_status_actor",None))
