from django.conf import settings
from django.utils import timezone
def institution(request):
    from academics.institution import InstitutionSettings
    branding=InstitutionSettings.objects.defer("logo").filter(pk=1).first()
    return {"ai_enabled":settings.FTBI_AI_ENABLED,"public_admissions_enabled":settings.FTBI_PUBLIC_ADMISSIONS,"institution_name":branding.name if branding else settings.FTBI_INSTITUTION_NAME,"institution_short_name":branding.short_name if branding else settings.FTBI_INSTITUTION_SHORT_NAME,"branding":branding,"portal_preference":getattr(request,"portal_preference",None),"display_timezone":timezone.get_current_timezone_name()}
