"""Optional institutional OpenID Connect integration."""
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

class InstitutionalOIDCBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        # Link by an explicitly provisioned, immutable provider subject, never email.
        from academics.identity_models import IdentityLink
        subject=claims.get("sub")
        if not isinstance(subject,str) or not subject:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(institutional_identity__subject=subject,is_active=True)
    def verify_claims(self, claims):
        return isinstance(claims.get("sub"),str) and bool(claims["sub"])
    def create_user(self, claims):
        raise SuspiciousOperation("Institutional accounts must be provisioned by administrators.")
    def update_user(self,user,claims):
        return user
