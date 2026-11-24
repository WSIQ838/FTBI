from datetime import timedelta
from random import SystemRandom
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render,get_object_or_404,redirect
from django.utils import timezone
from django.http import HttpResponseForbidden
from .quizzes import Quiz,Attempt,AttemptAnswer
from .timing import QuizPolicy,QuizSession
from .exam_extensions import ExamAccommodation
from .assessment_engine import answer_form, evaluate, attempt_grade
from .operations import AuditEvent

@login_required
def quizzes(request):
    available=Quiz.objects.filter(published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    return render(request,"quizzes.html",{"quizzes":available,"results":[(q,attempt_grade(q,request.user)) for q in available],"attempts":Attempt.objects.filter(student=request.user).select_related("quiz").order_by("quiz_id","number")})

@login_required
@transaction.atomic
def take_quiz(request,pk):
    quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=pk,published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    accommodation=ExamAccommodation.objects.filter(quiz=quiz,student=request.user).first()
    close=max(quiz.closes,accommodation.extended_close) if accommodation and accommodation.extended_close else quiz.closes
    policy=QuizPolicy.objects.filter(quiz=quiz).first()
    allowed=(policy.max_attempts if policy else 1)+(min(5,accommodation.extra_attempts) if accommodation else 0)
    now=timezone.now()
    attempts=Attempt.objects.filter(quiz=quiz,student=request.user)
    number=attempts.count()+1
    if number>allowed or now>=close:
        return HttpResponseForbidden("Quiz closed or attempt limit reached.")
    ids=list(quiz.questions.order_by("pk").values_list("pk",flat=True))
    if not ids:
        return HttpResponseForbidden("Quiz has no questions.")
    if policy and policy.shuffle:
        SystemRandom().shuffle(ids)
    if policy and policy.select_count:
        if policy.select_count > len(ids):
            return HttpResponseForbidden("Question pool is too small. Contact your instructor.")
        ids=SystemRandom().sample(ids,policy.select_count)
    duration=max(1,policy.minutes)+(min(720,accommodation.extra_minutes) if accommodation else 0) if policy else None
    expiry=min(close,now+timedelta(minutes=duration)) if duration else close
    session,_=QuizSession.objects.get_or_create(quiz=quiz,student=request.user,number=number,defaults={"started":now,"expires":expiry,"question_ids":ids})
    if timezone.now()>=session.expires:
        return HttpResponseForbidden("Assessment time expired; contact your instructor.")
    lookup={q.pk:q for q in quiz.questions.all()}
    if not set(session.question_ids).issubset(lookup):
        return HttpResponseForbidden("Assessment changed; contact your instructor.")
    questions=[lookup[i] for i in session.question_ids]
    form=answer_form(questions,request.POST if request.method=="POST" else None)
    context={"quiz":quiz,"form":form,"session":session,"number":number}
    if request.method=="POST":
        # Stale browser submissions cannot count as a new attempt.
        if request.POST.get("attempt_number")!=str(number):
            return HttpResponseForbidden("This assessment form is no longer current.")
        if not form.is_valid():
            return render(request,"take_quiz.html",context,status=400)
        if timezone.now()>=min(close,session.expires):
            return HttpResponseForbidden("Assessment time expired.")
        results=[(q,*evaluate(q,form.cleaned_data)) for q in questions]
        attempt=Attempt.objects.create(quiz=quiz,student=request.user,number=number,score=sum(score or 0 for _,_,score in results),total=sum(q.points for q in questions),graded=all(score is not None for _,_,score in results))
        AttemptAnswer.objects.bulk_create([AttemptAnswer(attempt=attempt,question=q,response=answer,possible=q.points,earned=score) for q,answer,score in results])
        AuditEvent.objects.create(actor=request.user,action="exam_submitted",target=str(attempt.pk))
        return redirect("quizzes")
    return render(request,"take_quiz.html",context)
