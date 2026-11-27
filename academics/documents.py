from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from .registrar import Application
from .models import Submission

class PrivateDocument(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    title=models.CharField(max_length=200)
    kind=models.CharField(max_length=16,choices=[("student","Student record"),("admission","Application"),("institution","Institutional library"),("coursework","Coursework")])
    application=models.ForeignKey(Application,on_delete=models.PROTECT,null=True,blank=True)
    submission=models.ForeignKey(Submission,on_delete=models.PROTECT,null=True,blank=True)
    published=models.BooleanField(default=False)
    created=models.DateTimeField(auto_now_add=True)

class DocumentVersion(models.Model):
    purged_at=models.DateTimeField(null=True,blank=True,editable=False)
    document=models.ForeignKey(PrivateDocument,on_delete=models.PROTECT,related_name="versions")
    number=models.PositiveIntegerField()
    original_name=models.CharField(max_length=200)
    data=models.BinaryField(editable=False)
    size=models.PositiveIntegerField()
    sha256=models.CharField(max_length=64)
    uploaded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    uploaded=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["document","number"],name="unique_document_version")]
        ordering=["-number"]

class DocumentVerification(models.Model):
    version=models.OneToOneField(DocumentVersion,on_delete=models.PROTECT,related_name="verification")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=12,choices=[("verified","Verified"),("rejected","Rejected")])
    note=models.TextField(max_length=2000)
    created=models.DateTimeField(auto_now_add=True)

class StorageQuota(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    limit_bytes=models.PositiveBigIntegerField(default=104857600,validators=[MinValueValidator(1)])

def storage_used(user):
    from django.db.models import Sum
    from django.db.models.functions import Length
    from .attachments import SubmissionAttachment
    from .assessment_policy import SubmissionRevision
    return ((DocumentVersion.objects.filter(document__owner=user,purged_at__isnull=True).aggregate(n=Sum("size"))["n"] or 0)
        +(SubmissionAttachment.objects.filter(submission__student=user).aggregate(n=Sum("size"))["n"] or 0)
        +(SubmissionRevision.objects.filter(submission__student=user).aggregate(n=Sum(Length("attachment_data")))["n"] or 0))

def document_access(user,document):
    if document.kind=="institution": return document.published or user.has_perm("academics.change_privatedocument")
    if document.kind=="coursework":
        from .models import Enrollment
        course=document.submission.assignment.course
        return course.instructor_id==user.pk or (document.owner_id==user.pk and course.published and Enrollment.objects.filter(student=user,course=course,active=True).exists())
    if document.owner_id==user.pk: return True
    if document.kind=="student": return user.has_perms(["academics.view_privatedocument","academics.view_studentprofile"])
    from .admissions_support import reviewable
    return reviewable(user).filter(pk=document.application_id).exists()
