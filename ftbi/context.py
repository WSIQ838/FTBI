from django.conf import settings
def institution(request):
    return {"public_admissions_enabled":settings.FTBI_PUBLIC_ADMISSIONS,"institution_name":settings.FTBI_INSTITUTION_NAME,"institution_short_name":settings.FTBI_INSTITUTION_SHORT_NAME}
