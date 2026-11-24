from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from .quizzes import Quiz, Attempt
from .timing import QuizPolicy
from .operations import AuditEvent


class QuizPolicyForm(forms.ModelForm):
    class Meta:
        model=QuizPolicy
        fields=["minutes","shuffle","max_attempts","select_count","attempt_rule"]


@login_required
@transaction.atomic
def exam_policy(request, pk):
    quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=pk,course__instructor=request.user)
    if quiz.quizsession_set.exists() or quiz.attempt_set.exists():
        return HttpResponseForbidden("Assessment policy is locked after a session starts.")
    policy=QuizPolicy.objects.filter(quiz=quiz).first() or QuizPolicy(quiz=quiz)
    form=QuizPolicyForm(request.POST if request.method=="POST" else None,instance=policy)
    if request.method=="POST" and form.is_valid():
        if form.cleaned_data["select_count"]>quiz.questions.count():
            form.add_error("select_count","Selection exceeds the available question pool.")
        else:
            form.save()
            AuditEvent.objects.create(actor=request.user,action="exam_policy_updated",target=str(pk))
            return redirect("faculty",pk=quiz.course_id)
    return render(request,"form.html",{"form":form,"heading":"Assessment policy: "+quiz.title})


@login_required
def exam_queue(request,pk):
    quiz=get_object_or_404(Quiz,pk=pk,course__instructor=request.user)
    return render(request,"exam_queue.html",{"quiz":quiz,"attempts":quiz.attempt_set.select_related("student").order_by("graded","pk")})


@login_required
@transaction.atomic
def grade_attempt(request,pk):
    attempt=get_object_or_404(Attempt.objects.select_for_update(),pk=pk,quiz__course__instructor=request.user)
    answers=list(attempt.answers.select_related("question").order_by("pk"))
    if not answers:
        return HttpResponseForbidden("Legacy attempts have no question-level answers and cannot be regraded here.")
    form=forms.Form(request.POST if request.method=="POST" else None)
    for answer in answers:
        form.fields[f"score_{answer.pk}"]=forms.DecimalField(label=f"{answer.question.prompt}: {answer.response}",min_value=0,max_value=answer.possible,decimal_places=2,initial=answer.earned)
        form.fields[f"feedback_{answer.pk}"]=forms.CharField(label="Feedback",required=False,widget=forms.Textarea,initial=answer.feedback,max_length=10000)
    if request.method=="POST" and form.is_valid():
        for answer in answers:
            answer.earned=form.cleaned_data[f"score_{answer.pk}"]
            answer.feedback=form.cleaned_data[f"feedback_{answer.pk}"]
            answer.save(update_fields=["earned","feedback"])
        attempt.score=sum(a.earned for a in answers)
        attempt.graded=True
        attempt.save(update_fields=["score","graded"])
        AuditEvent.objects.create(actor=request.user,action="exam_graded",target=str(pk))
        return redirect("exam_queue",pk=attempt.quiz_id)
    return render(request,"form.html",{"form":form,"heading":f"Grade {attempt.quiz.title}: {attempt.student} (attempt {attempt.number})"})
