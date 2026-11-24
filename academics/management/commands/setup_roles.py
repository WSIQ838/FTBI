from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

ROLES={
    "AI Administration":["aiconfiguration","aiusage","knowledgedocument"],
    "Security Administration":["accountsecurity","accountsession","securityincident","durablenotification","accountcontrolevent"],
    "Registrar":["studentprofile","registrationwindow","waitlistentry","prerequisite","application","enrollment","finalgrade","transfercredit","transcriptrequest","issuedtranscript","graduationapplication","degreerequirement","examaccommodation","advisorassignment","issueddiploma"],
    "Academic Advisor":["advisorassignment"],
    "Admissions":["application"],
    "IT Audit":["auditevent"],
    "Finance":["ledgerentry","financialaidaward","paymentrequest","invoice","paymentallocation","paymentplan","installment","tuitionschedule"],
    "Academic Administration":["department","program","term","course","gradecategory","assignmentweight","attendance","learningoutcome","practicum","announcement","calendarevent","libraryresource"],
    "Institutional Reporting":["studentprofile","enrollment","application"],
}
class Command(BaseCommand):
    help="Create institutional groups with explicit model permissions. Assign staff membership separately."
    def handle(self,*args,**kwargs):
        for name,models in ROLES.items():
            group,_=Group.objects.get_or_create(name=name)
            permissions=Permission.objects.filter(content_type__app_label="academics",content_type__model__in=models)
            if name in ("Institutional Reporting","IT Audit","Academic Advisor"):
                permissions=permissions.filter(codename__startswith="view_")
            else:
                permissions=permissions.exclude(codename__startswith="delete_")
            group.permissions.set(permissions)
            self.stdout.write(name)
