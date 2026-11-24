from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
import django.core.validators

class Migration(migrations.Migration):
    dependencies=[("academics","0002_advising_diplomas"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.RemoveConstraint(model_name="attempt",name="one_quiz_attempt"),
        migrations.RemoveConstraint(model_name="quizsession",name="unique_quiz_session"),
        migrations.AddField(model_name="attempt",name="number",field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="quizsession",name="number",field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddConstraint(model_name="attempt",constraint=models.UniqueConstraint(fields=("quiz","student","number"),name="unique_numbered_attempt")),
        migrations.AddConstraint(model_name="quizsession",constraint=models.UniqueConstraint(fields=("quiz","student","number"),name="unique_numbered_session")),
        migrations.CreateModel(name="ExamAccommodation",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("extra_minutes",models.PositiveIntegerField(default=0,validators=[django.core.validators.MaxValueValidator(720)])),("extra_attempts",models.PositiveSmallIntegerField(default=0,validators=[django.core.validators.MaxValueValidator(5)])),("extended_close",models.DateTimeField(blank=True,null=True)),("quiz",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to="academics.quiz")),("student",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))],options={"constraints":[models.UniqueConstraint(fields=("quiz","student"),name="unique_exam_accommodation")]}),
        migrations.CreateModel(name="BankQuestion",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("prompt",models.TextField()),("option_a",models.CharField(max_length=500)),("option_b",models.CharField(max_length=500)),("option_c",models.CharField(max_length=500)),("option_d",models.CharField(max_length=500)),("correct",models.CharField(choices=[("A","A"),("B","B"),("C","C"),("D","D")],max_length=1)),("owner",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))])
    ]
