from datetime import timedelta
from random import SystemRandom
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render,get_object_or_404,redirect
from django.utils import timezone
from django.http import HttpResponseForbidden
from .quizzes import Quiz,Attempt
from .timing import QuizPolicy,QuizSession
from .exam_extensions import ExamAccommodation

@login_required
def quizzes(request):
    available=Quiz.objects.filter(published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    return render(request,"quizzes.html",{"quizzes":available,"attempts":Attempt.objects.filter(student=request.user).select_related("quiz").order_by("quiz_id","number")})

@login_required
@transaction.atomic
def take_quiz(request,pk):
    quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=pk,published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    accommodation=ExamAccommodation.objects.filter(quiz=quiz,student=request.user).first()
    close=max(quiz.closes,accommodation.extended_close) if accommodation and accommodation.extended_close else quiz.closes
    allowed=1+min(5,accommodation.extra_attempts) if accommodation else 1
    now=timezone.now()
    attempts=Attempt.objects.filter(quiz=quiz,student=request.user)
    number=attempts.count()+1
    if number>allowed or now>=close:
        return HttpResponseForbidden("Quiz closed or attempt limit reached.")
    policy=QuizPolicy.objects.filter(quiz=quiz).first()
    ids=list(quiz.questions.order_by("pk").values_list("pk",flat=True))
    if not ids:
        return HttpResponseForbidden("Quiz has no questions.")
    if policy and policy.shuffle:
        SystemRandom().shuffle(ids)
    duration=max(1,policy.minutes)+(min(720,accommodation.extra_minutes) if accommodation else 0) if policy else None
    expiry=min(close,now+timedelta(minutes=duration)) if duration else close
    session,_=QuizSession.objects.get_or_create(quiz=quiz,student=request.user,number=number,defaults={"started":now,"expires":expiry,"question_ids":ids})
    if timezone.now()>=session.expires:
        return HttpResponseForbidden("Assessment time expired; contact your instructor.")
    lookup={q.pk:q for q in quiz.questions.all()}
    if set(lookup)!=set(session.question_ids):
        return HttpResponseForbidden("Assessment changed; contact your instructor.")
    questions=[lookup[i] for i in session.question_ids]
    context={"quiz":quiz,"questions":questions,"session":session,"number":number}
    if request.method=="POST":
        # Stale browser submissions cannot count as a new attempt.
        if request.POST.get("attempt_number")!=str(number):
            return HttpResponseForbidden("This assessment form is no longer current.")
        answers=[request.POST.get("q"+str(q.pk)) for q in questions]
        if any(a not in ("A","B","C","D") for a in answers):
            return render(request,"take_quiz.html",{**context,"error":"Answer every question."},status=400)
        if timezone.now()>=min(close,session.expires):
            return HttpResponseForbidden("Assessment time expired.")
        Attempt.objects.create(quiz=quiz,student=request.user,number=number,score=sum(a==q.correct for a,q in zip(answers,questions)),total=len(questions))
        return redirect("quizzes")
    return render(request,"take_quiz.html",context)
