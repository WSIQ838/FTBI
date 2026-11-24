from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render,get_object_or_404,redirect
from django.utils import timezone
from django.http import HttpResponseForbidden
from .models import Enrollment
from .quizzes import Quiz,Attempt

@login_required
def quizzes(request):
    available=Quiz.objects.filter(published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    return render(request,"quizzes.html",{"quizzes":available,"attempts":Attempt.objects.filter(student=request.user).select_related("quiz")})

@login_required
def take_quiz(request,pk):
    quiz=get_object_or_404(Quiz,pk=pk,published=True,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    if Attempt.objects.filter(quiz=quiz,student=request.user).exists() or timezone.now()>=quiz.closes:
        return HttpResponseForbidden("Quiz is closed or already submitted.")
    questions=list(quiz.questions.order_by("pk"))
    if not questions:
        return HttpResponseForbidden("Quiz has no questions.")
    if request.method=="POST":
        answers=[request.POST.get("q"+str(q.pk)) for q in questions]
        if any(a not in ("A","B","C","D") for a in answers):
            return render(request,"take_quiz.html",{"quiz":quiz,"questions":questions,"error":"Answer every question."},status=400)
        with transaction.atomic():
            attempt,created=Attempt.objects.get_or_create(quiz=quiz,student=request.user,defaults={"score":sum(a==q.correct for a,q in zip(answers,questions)),"total":len(questions)})
        return redirect("quizzes")
    return render(request,"take_quiz.html",{"quiz":quiz,"questions":questions})
