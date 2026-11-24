from django.conf import settings
from django.db import models
from .models import Course

class Discussion(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="discussions")
    title=models.CharField(max_length=180)
    prompt=models.TextField()
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)
    closed=models.BooleanField(default=False)

class DiscussionReply(models.Model):
    discussion=models.ForeignKey(Discussion,on_delete=models.CASCADE,related_name="replies")
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    body=models.TextField()
    created=models.DateTimeField(auto_now_add=True)
