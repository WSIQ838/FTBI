from django.conf import settings
from django.core.checks import Error,Tags,register


@register(Tags.security,deploy=True)
def passkey_configuration_check(app_configs,**kwargs):
    if not settings.FTBI_PASSKEYS_ENABLED: return []
    from .passkeys import configuration
    try: configuration()
    except ValueError:
        return [Error("Passkeys require an approved HTTPS origin and matching DNS relying-party ID.",id="ftbi.E001")]
    return []
