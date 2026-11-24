from django.conf import settings
def institution(request):
    return {"institution_name":settings.FTBI_INSTITUTION_NAME,"institution_short_name":settings.FTBI_INSTITUTION_SHORT_NAME}
