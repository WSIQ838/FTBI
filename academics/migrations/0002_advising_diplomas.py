import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[("academics","0001_initial"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="AdvisorAssignment",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("active",models.BooleanField(default=True)),("advisor",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),("student",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="advisor_assignments",to="academics.studentprofile"))],options={"constraints":[models.UniqueConstraint(fields=("student","advisor"),name="unique_advisor_assignment")]}),
        migrations.CreateModel(name="IssuedDiploma",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("identifier",models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),("issued_at",models.DateTimeField(auto_now_add=True)),("recipient",models.CharField(max_length=300)),("program",models.CharField(max_length=200)),("institution",models.CharField(max_length=200)),("application",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,to="academics.graduationapplication")),("issued_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))])
    ]
