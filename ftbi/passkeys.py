import hashlib
import json
import secrets
import re
import ipaddress
from datetime import timedelta
from urllib.parse import urlparse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction,IntegrityError
from django.http import JsonResponse,HttpResponseForbidden,HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from webauthn import generate_registration_options,generate_authentication_options,verify_registration_response,verify_authentication_response
from webauthn.helpers import options_to_json,bytes_to_base64url,base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import AuthenticatorSelectionCriteria,ResidentKeyRequirement,UserVerificationRequirement,PublicKeyCredentialDescriptor
from academics.passkeys import PasskeyIdentity,PasskeyDevice,PasskeyChallenge
from academics.operations import AuditEvent
from academics.notification_models import notify


def configuration():
    if not settings.FTBI_PASSKEYS_ENABLED: raise ValueError("Passkeys disabled")
    rp=settings.FTBI_PASSKEY_RP_ID;origin=settings.FTBI_PASSKEY_ORIGIN
    parsed=urlparse(origin)
    if not re.fullmatch(r"[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?",rp) or any(not part or len(part)>63 or part.startswith("-") or part.endswith("-") for part in rp.split(".")):
        raise ValueError("Invalid relying party hostname")
    try: ipaddress.ip_address(rp)
    except ValueError: pass
    else: raise ValueError("Use a DNS hostname")
    if rp=="localhost" and not settings.DEBUG: raise ValueError("Localhost is only for development")
    if not rp or len(rp)>253 or not rp.isascii() or parsed.hostname!=rp or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Invalid relying party configuration")
    if parsed.scheme!="https" and not (settings.DEBUG and parsed.scheme=="http" and rp=="localhost"):
        raise ValueError("HTTPS origin required")
    if parsed.port is not None and not 1<=parsed.port<=65535: raise ValueError("Invalid port")
    default_port=443 if parsed.scheme=="https" else 80
    canonical=f"{parsed.scheme}://{rp}"+(f":{parsed.port}" if parsed.port not in {None,default_port} else "")
    if origin!=canonical: raise ValueError("Use the canonical origin without a trailing slash or default port")
    return rp,origin


def has_factor(user):
    return TOTPDevice.objects.filter(user=user,confirmed=True).exists() or PasskeyDevice.objects.filter(user=user,confirmed=True).exists()


def may_enroll(user): return user.is_verified() or not has_factor(user)


def session_digest(request):
    if not request.session.session_key: request.session.save()
    return hashlib.sha256(request.session.session_key.encode()).hexdigest()


def limited(user):
    key=f"passkey-ceremony:{user.pk}"
    cache.add(key,0,300)
    try: return cache.incr(key)>30
    except ValueError: return True


def failure(status=400): return JsonResponse({"error":"Passkey verification failed. Start again or use another verification method."},status=status)


@login_required
def manage(request):
    try: configuration()
    except ValueError: return HttpResponse("Passkeys are unavailable. Use your authenticator or recovery code, or contact support.",status=503)
    if not may_enroll(request.user): return redirect("mfa_verify")
    return render(request,"passkeys.html",{"devices":PasskeyDevice.objects.filter(user=request.user,confirmed=True),"enroll":True})


@login_required
def verify(request):
    try: configuration()
    except ValueError: return render(request,"passkeys.html",{"unavailable":True},status=503)
    if request.user.is_verified(): return redirect("dashboard")
    if not PasskeyDevice.objects.filter(user=request.user,confirmed=True).exists(): return redirect("mfa_setup")
    return render(request,"passkeys.html",{"verify":True})


@login_required
@require_POST
@sensitive_post_parameters("password")
@transaction.atomic
def begin(request,purpose):
    try: rp,origin=configuration()
    except ValueError: return failure(503)
    if purpose not in {"register","authenticate"}: return failure()
    if limited(request.user): return failure(429)
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    devices=list(PasskeyDevice.objects.filter(user=request.user,confirmed=True))
    identity,_=PasskeyIdentity.objects.get_or_create(user=request.user)
    if purpose=="register":
        label=request.POST.get("label","").strip()
        if not may_enroll(request.user) or not request.user.check_password(request.POST.get("password","")): return failure(403)
        if not 1<=len(label)<=64 or len(devices)>=8 or PasskeyDevice.objects.filter(user=request.user).count()>=64: return failure()
    else:
        label=""
        if not devices: return failure(403)
    challenge=secrets.token_bytes(32)
    PasskeyChallenge.objects.update_or_create(user=request.user,defaults={"challenge":challenge,"session_digest":session_digest(request),"purpose":purpose,"expires":timezone.now()+timedelta(minutes=5),"consumed":False,"rp_id":rp,"origin":origin,"label":label})
    descriptors=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(device.credential_id)) for device in devices]
    if purpose=="register":
        options=generate_registration_options(rp_id=rp,rp_name="FTBI",user_id=bytes(identity.handle),user_name=request.user.username,
            challenge=challenge,exclude_credentials=descriptors,authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED,user_verification=UserVerificationRequirement.REQUIRED))
    else:
        options=generate_authentication_options(rp_id=rp,challenge=challenge,allow_credentials=descriptors,user_verification=UserVerificationRequirement.REQUIRED)
    return JsonResponse(json.loads(options_to_json(options)))


@login_required
@require_POST
@transaction.atomic
def finish(request,purpose):
    try: rp,origin=configuration()
    except ValueError: return failure(503)
    if purpose not in {"register","authenticate"}: return failure()
    if limited(request.user): return failure(429)
    if len(request.body)>32768: return failure(413)
    try:
        credential=json.loads(request.body)
        if not isinstance(credential,dict) or not isinstance(credential.get("response"),dict): return failure()
    except (ValueError,RecursionError): return failure()
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    challenge=PasskeyChallenge.objects.select_for_update().filter(user=request.user).first()
    if not challenge or challenge.consumed or challenge.expires<=timezone.now() or challenge.purpose!=purpose or challenge.session_digest!=session_digest(request) or (challenge.rp_id,challenge.origin)!=(rp,origin): return failure()
    challenge.consumed=True;challenge.save(update_fields=["consumed"])
    device=None
    try:
        client_data=json.loads(base64url_to_bytes(credential["response"]["clientDataJSON"]))
        if not isinstance(client_data,dict) or client_data.get("crossOrigin",False) is not False or client_data.get("topOrigin") is not None: return failure()
        if purpose=="register":
            if not may_enroll(request.user) or PasskeyDevice.objects.filter(user=request.user,confirmed=True).count()>=8: return failure(403)
            result=verify_registration_response(credential=credential,expected_challenge=bytes(challenge.challenge),expected_rp_id=rp,expected_origin=origin,require_user_presence=True,require_user_verification=True)
            identifier=bytes_to_base64url(result.credential_id)
            if len(result.credential_id)>1024 or PasskeyDevice.objects.filter(credential_id=identifier).exists(): return failure()
        else:
            identifier=credential.get("id")
            if not isinstance(identifier,str) or len(identifier)>1400: return failure()
            device=PasskeyDevice.objects.select_for_update().filter(user=request.user,confirmed=True,credential_id=identifier).first()
            if not device: return failure()
            handle=credential["response"].get("userHandle")
            identity=PasskeyIdentity.objects.filter(user=request.user).first()
            if not identity or (handle is not None and base64url_to_bytes(handle)!=bytes(identity.handle)): return failure()
            result=verify_authentication_response(credential=credential,expected_challenge=bytes(challenge.challenge),expected_rp_id=rp,expected_origin=origin,credential_public_key=bytes(device.public_key),credential_current_sign_count=device.sign_count,require_user_verification=True)
            if device.backup_eligible!=(result.credential_device_type.value=="multi_device"): return failure()
    except (WebAuthnException,ValueError,TypeError,KeyError,RecursionError): return failure()
    # Database and notification failures propagate, rolling back the whole ceremony.
    if purpose=="register":
        try:
            with transaction.atomic():
                device=PasskeyDevice.objects.create(user=request.user,name=challenge.label,credential_id=identifier,public_key=result.credential_public_key,sign_count=result.sign_count,backed_up=result.credential_backed_up,backup_eligible=result.credential_device_type.value=="multi_device",last_used=timezone.now())
        except IntegrityError: return failure()
        event=AuditEvent.objects.create(actor=request.user,action="passkey_registered",target=str(device.pk))
        notify(request.user,"security","Passkey added","A passkey was added to your account. Review account security if you did not make this change.",f"passkey-added:{event.pk}")
    else:
        device.sign_count=result.new_sign_count;device.backed_up=result.credential_backed_up;device.last_used=timezone.now()
        device.save(update_fields=["sign_count","backed_up","last_used"])
        AuditEvent.objects.create(actor=request.user,action="passkey_verified",target=str(device.pk))
    otp_login(request,device);request.session.cycle_key()
    return JsonResponse({"ok":True})


@login_required
@require_POST
@sensitive_post_parameters("password")
@transaction.atomic
def revoke(request,pk):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    if not request.user.is_verified() or not request.user.check_password(request.POST.get("password","")): return HttpResponseForbidden("Verify MFA and confirm your password before revoking a passkey.")
    device=get_object_or_404(PasskeyDevice.objects.select_for_update(),pk=pk,user=request.user,confirmed=True)
    device.confirmed=False;device.revoked_at=timezone.now();device.save(update_fields=["confirmed","revoked_at"])
    event=AuditEvent.objects.create(actor=request.user,action="passkey_revoked",target=str(device.pk))
    notify(request.user,"security","Passkey revoked","A passkey was revoked from your account.",f"passkey-revoked:{event.pk}")
    return redirect("passkey_manage")
