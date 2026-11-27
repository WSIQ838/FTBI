"""Capture public-facing decision text atomically with the admissions decision."""
from django.utils import timezone
from .credentials import CredentialTemplate
from .institution import institution_name


def capture_letter(application,status):
    kind={"accepted":"acceptance","rejected":"rejection"}[status]
    template=CredentialTemplate.objects.filter(kind=kind,enabled=True).first()
    if template: template.full_clean()
    now=timezone.now()
    values={"recipient":application.applicant.get_full_name() or application.applicant.username,
            "program":application.program.name,"institution":institution_name(),
            "issued_date":str(now.date()),"identifier":str(application.pk)}
    default_body=("Your application to {program} has been accepted. Contact admissions to confirm enrollment requirements and next steps."
                  if status=="accepted" else "Your application to {program} was not accepted. Contact admissions for information about available options.")
    wording={"heading":template.heading if template else "Admissions decision",
             "body":template.body if template else default_body,"footer":template.footer if template else "Admissions office"}
    return {**values,"status":status,"issued_at":now.isoformat(),
            "template":{**wording,"approval_reference":template.approval_reference if template else "",
                        "template_id":template.pk if template else None},
            "text":{key:value.format_map(values) for key,value in wording.items()}}
