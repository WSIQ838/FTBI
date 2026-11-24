from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.db import transaction
from .models import Course
from .quizzes import Quiz,Question
from .exam_extensions import BankQuestion
class BankForm(forms.ModelForm):
    class Meta:
        model=BankQuestion
        fields=["prompt","option_a","option_b","option_c","option_d","correct"]
@login_required
def bank(request):
    if not Course.objects.filter(instructor=request.user).exists():
        return HttpResponseForbidden()
    form=BankForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        q=form.save(commit=False)
        q.owner=request.user
        q.save()
        return redirect("question_bank")
    return render(request,"bank.html",{"form":form,"questions":BankQuestion.objects.filter(owner=request.user)})
@login_required
def import_question(request,pk):
    quiz=get_object_or_404(Quiz,pk=pk,course__instructor=request.user)
    choices=BankQuestion.objects.filter(owner=request.user)
    if request.method=="POST":
        with transaction.atomic():
            quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=pk,course__instructor=request.user)
            if quiz.published or quiz.attempt_set.exists() or quiz.quizsession_set.exists():
                return HttpResponseForbidden("Assessment questions are locked.")
            q=get_object_or_404(choices,pk=request.POST.get("question",0))
            Question.objects.create(quiz=quiz,**{field:getattr(q,field) for field in BankForm.Meta.fields})
        return redirect("faculty",pk=quiz.course_id)
    return render(request,"bank_import.html",{"questions":choices,"quiz":quiz})
