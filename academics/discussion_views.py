from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,render,redirect
from django.http import HttpResponseForbidden
from django.db import transaction
from .views import visible_courses
from .discussions import Discussion,DiscussionReply

class TopicForm(forms.ModelForm):
    class Meta:
        model=Discussion
        fields=["title","prompt"]

class ReplyForm(forms.ModelForm):
    class Meta:
        model=DiscussionReply
        fields=["body"]

@login_required
def discussions(request,pk):
    course=get_object_or_404(visible_courses(request.user),pk=pk)
    teaching=course.instructor_id==request.user.pk
    form=TopicForm(request.POST if request.method=="POST" else None)
    if request.method=="POST":
        if not teaching:
            return HttpResponseForbidden()
        if form.is_valid():
            topic=form.save(commit=False)
            topic.course=course
            topic.author=request.user
            topic.save()
            return redirect("discussions",pk=pk)
    return render(request,"discussions.html",{"course":course,"topics":course.discussions.order_by("-created"),"form":form,"teaching":teaching})

@login_required
def discussion(request,pk):
    topic=get_object_or_404(Discussion.objects.select_related("course"),pk=pk,course__in=visible_courses(request.user))
    form=ReplyForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            locked=Discussion.objects.select_for_update().get(pk=topic.pk)
            if locked.closed:
                return HttpResponseForbidden("Discussion is closed.")
            reply=form.save(commit=False)
            reply.discussion=locked
            reply.author=request.user
            reply.save()
        return redirect("discussion",pk=pk)
    return render(request,"discussion.html",{"topic":topic,"form":form,"replies":topic.replies.select_related("author").order_by("created")})
