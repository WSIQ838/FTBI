from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.shortcuts import render,redirect,get_object_or_404
from django import forms
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Course,Enrollment,Program
from .registrar import StudentProfile,Application
from .operations import FinancialAidAward,TransferCredit,TranscriptRequest,Message,AuditEvent

def contacts(user):
    U=get_user_model()
    ids=set(Enrollment.objects.filter(course__instructor=user,active=True).values_list("student_id",flat=True))
    ids.update(Course.objects.filter(enrollments__student=user,enrollments__active=True,published=True).values_list("instructor_id",flat=True))
    return U.objects.filter(pk__in=ids,is_active=True).exclude(pk=user.pk)

class MessageForm(forms.ModelForm):
    class Meta:
        model=Message
        fields=["recipient","subject","body"]
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["recipient"].queryset=contacts(user)

class RequestForm(forms.ModelForm):
    class Meta:
        model=TranscriptRequest
        fields=["destination"]

@login_required
def inbox(request):
    form=MessageForm(request.POST if request.method=="POST" else None,user=request.user)
    if request.method=="POST" and form.is_valid():
        m=form.save(commit=False)
        m.sender=request.user
        m.save()
        return redirect("inbox")
    return render(request,"inbox.html",{"form":form,"messages_list":Message.objects.filter(Q(sender=request.user)|Q(recipient=request.user)).select_related("sender","recipient").order_by("-sent")[:100]})

@login_required
@require_POST
def mark_read(request,pk):
    Message.objects.filter(pk=pk,recipient=request.user,read__isnull=True).update(read=timezone.now())
    return redirect("inbox")

@login_required
def records(request):
    profile=get_object_or_404(StudentProfile,user=request.user)
    form=RequestForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        item=form.save(commit=False)
        item.student=profile
        item.save()
        AuditEvent.objects.create(actor=request.user,action="transcript_requested",target=str(item.pk))
        return redirect("records")
    return render(request,"records.html",{"form":form,"requests":TranscriptRequest.objects.filter(student=profile),"aid":FinancialAidAward.objects.filter(student=profile,visible=True),"transfers":TransferCredit.objects.filter(student=profile,approved=True)})

@login_required
@permission_required("academics.view_studentprofile",raise_exception=True)
@permission_required("academics.view_enrollment",raise_exception=True)
@permission_required("academics.view_application",raise_exception=True)
def reports(request):
    return render(request,"reports.html",{"students":StudentProfile.objects.count(),"enrollments":Enrollment.objects.filter(active=True).count(),"applications":Application.objects.values("status").annotate(total=Count("id")),"programs":Program.objects.annotate(total=Count("studentprofile"))})
