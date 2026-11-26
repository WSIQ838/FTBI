from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

ROLES={
    "Reporting Access Administration":["deanassignment"],
    "Scholarship Administration":["scholarshipfund","scholarshipapplication","scholarshipaward","scholarshipevent"],
    "Institution Administration":["institutionsettings","campus"],
    "Accommodation Administration":["studentaccommodation"],
    "AI Administration":["aiconfiguration","aiusage","knowledgedocument"],
    "Security Administration":["accountsecurity","accountsession","securityincident","durablenotification","accountcontrolevent"],
    "Registrar":["credentialtemplate","credentialartifact","credentialrevocation","credentialreplacement","privatedocument","documentverification","storagequota","withdrawalwindow","withdrawalrequest","gradingscale","standingpolicy","academicstanding","emergencycontact","studentstatusrecord","enrollmentverification","studentprofile","registrationwindow","waitlistentry","prerequisite","application","enrollment","finalgrade","transfercredit","transcriptrequest","issuedtranscript","graduationapplication","degreerequirement","examaccommodation","advisorassignment","issueddiploma"],
    "Academic Advisor":["advisorassignment"],
    "Admissions":["application","applicationnote","admissioninterview","documentverification","privatedocument"],
    "Admissions Managers":["applicationreviewer"],
    "IT Audit":["auditevent"],
    "Finance":["paymentadjustment","allocationreduction","paymentdispute","financialholdpolicy","financialhold","ledgerentry","financialaidaward","paymentrequest","invoice","paymentallocation","paymentplan","installment","tuitionschedule"],
    "Academic Administration":["privatedocument","department","program","term","course","gradecategory","assignmentweight","attendance","learningoutcome","practicum","announcement","calendarevent","libraryresource"],
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

        report_permissions=["view_institutionalreport","add_institutionalreport","view_reportsnapshot","add_reportsnapshot"]
        for name,extra in [("President",["view_president_dashboard"]),("Dean",["view_dean_dashboard"]),("Report Reviewer",["review_report_snapshot","view_studentprofile","view_application","view_enrollment","view_finalgrade"])]:
            group,_=Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label="academics",codename__in=report_permissions+extra))
            self.stdout.write(name)
        group=Group.objects.get(name="Institutional Reporting")
        group.permissions.add(*Permission.objects.filter(content_type__app_label="academics",codename__in=report_permissions))
