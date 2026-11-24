from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.db import transaction
from .evaluations import EvaluationWindow,CourseEvaluation

class EvaluationForm(forms.ModelForm):
    class Meta:
        model=CourseEvaluation
        fields=["rating","comments"]

@login_required
def evaluations(request):
    now=timezone.now()
    windows=EvaluationWindow.objects.filter(opens__lte=now,closes__gt=now,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True).exclude(courseevaluation__student=request.user)
    return render(request,"evaluations.html",{"windows":windows})

@login_required
def evaluate(request,pk):
    now=timezone.now()
    window=get_object_or_404(EvaluationWindow,pk=pk,opens__lte=now,closes__gt=now,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    if CourseEvaluation.objects.filter(window=window,student=request.user).exists():
        return redirect("evaluations")
    form=EvaluationForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            CourseEvaluation.objects.get_or_create(window=window,student=request.user,defaults=form.cleaned_data)
        return redirect("evaluations")
    return render(request,"evaluate.html",{"form":form,"window":window})
