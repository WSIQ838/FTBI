from django import forms
from django.contrib.auth.decorators import login_required,permission_required
from django.shortcuts import render,redirect,get_object_or_404
from django.db import transaction
from .advising import AdvisorAssignment
from .services import AdvisingNote
from .degree_views import audit

class NoteForm(forms.Form):
    note=forms.CharField(max_length=4000,widget=forms.Textarea)

@login_required
@permission_required("academics.view_advisorassignment",raise_exception=True)
def caseload(request):
    assignments=AdvisorAssignment.objects.filter(advisor=request.user,active=True).select_related("student__user","student__program")
    return render(request,"caseload.html",{"assignments":assignments})

@login_required
@permission_required("academics.view_advisorassignment",raise_exception=True)
def advise(request,pk):
    assignment=get_object_or_404(AdvisorAssignment.objects.select_related("student__user","student__program"),pk=pk,advisor=request.user,active=True)
    form=NoteForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            locked=get_object_or_404(AdvisorAssignment.objects.select_for_update(),pk=pk,advisor=request.user,active=True)
            AdvisingNote.objects.create(student=locked.student,advisor=request.user,note=form.cleaned_data["note"])
        return redirect("advise",pk=pk)
    return render(request,"advise.html",{"assignment":assignment,"audit":audit(assignment.student),"notes":AdvisingNote.objects.filter(student=assignment.student,advisor=request.user).order_by("-created"),"form":form})
