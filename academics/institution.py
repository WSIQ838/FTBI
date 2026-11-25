import re
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

def luminance(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in rgb]
    return sum(c*w for c,w in zip(linear,[0.2126,0.7152,0.0722]))

def institution_name():
    return InstitutionSettings.objects.filter(pk=1).values_list("name",flat=True).first() or settings.FTBI_INSTITUTION_NAME

class InstitutionSettings(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    name=models.CharField(max_length=150)
    short_name=models.CharField(max_length=30)
    accent=models.CharField(max_length=7,default="#175b9a")
    header=models.CharField(max_length=7,default="#142844")
    logo=models.BinaryField(null=True,editable=False)
    logo_type=models.CharField(max_length=20,blank=True)
    updated=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(id=1),name="institution_settings_singleton")]
    def clean(self):
        for field in ["accent","header"]:
            value=getattr(self,field)
            if not re.fullmatch(r"#[0-9a-fA-F]{6}",value or ""): raise ValidationError({field:"Use a six-digit hexadecimal color."})
            backgrounds=["#ffffff","#f4f6fa"] if field=="accent" else ["#ffffff"]
            if any((luminance(bg)+0.05)/(luminance(value)+0.05)<4.5 for bg in backgrounds): raise ValidationError({field:"Choose a darker color with at least 4.5:1 text contrast."})

class PortalPreference(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    timezone=models.CharField(max_length=100,default="UTC")
    show_courses=models.BooleanField(default=True)
    show_services=models.BooleanField(default=True)
    course_order=models.CharField(max_length=12,default="code",choices=[("code","Course code"),("title","Course title"),("term","Newest term")])
    def clean(self):
        try: ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError,ValueError,TypeError): raise ValidationError({"timezone":"Select a valid timezone."})

class ImportBatch(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    kind=models.CharField(max_length=12,choices=[("students","Students"),("courses","Courses")])
    rows=models.JSONField()
    digest=models.CharField(max_length=64)
    created=models.DateTimeField(auto_now_add=True)
    committed_at=models.DateTimeField(null=True)
    created_ids=models.JSONField(default=list)
