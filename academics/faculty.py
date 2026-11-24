from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django import forms
from .models import Course, Lesson, Assignment
from .quizzes import Quiz, Question
from django.db import transaction

class CourseForm(forms.ModelForm):
    class Meta:
        model=Course
        fields=["syllabus","published"]

class LessonForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .learning import LearningModule
        self.fields["module"].queryset=LearningModule.objects.filter(course=self.instance.course)
    class Meta:
        model=Lesson
        fields=["title","body","position","module","video_url"]

class AssignmentForm(forms.ModelForm):
    class Meta:
        model=Assignment
        fields=["title","instructions","due"]

class QuizForm(forms.ModelForm):
    class Meta:
        model=Quiz
        fields=["title","closes","published","results_released"]

class QuestionForm(forms.ModelForm):
    class Meta:
        model=Question
        fields=["kind","prompt","points","option_a","option_b","option_c","option_d","correct","answer_key"]

@login_required
def faculty(request,pk):
    course=get_object_or_404(Course,pk=pk,instructor=request.user)
    return render(request,"faculty.html",{"course":course,"quizzes":Quiz.objects.filter(course=course)})

@login_required
@transaction.atomic
def author(request,pk,kind,item=0):
    course=get_object_or_404(Course.objects.select_for_update(),pk=pk,instructor=request.user)
    forms_by_kind={"course":(Course,CourseForm),"lesson":(Lesson,LessonForm),"assignment":(Assignment,AssignmentForm),"quiz":(Quiz,QuizForm)}
    if kind not in forms_by_kind:
        from django.http import Http404
        raise Http404()
    model,form_class=forms_by_kind[kind]
    if kind=="course":
        obj=course
    elif item:
        obj=get_object_or_404(model,pk=item,course=course)
    else:
        obj=model(course=course)
    form=form_class(request.POST if request.method=="POST" else None,instance=obj)
    if request.method=="POST" and form.is_valid():
        if kind=="lesson" and item:
            from .learning import LessonCompletion
            old=Lesson.objects.get(pk=item)
            if old.module_id!=form.instance.module_id and LessonCompletion.objects.filter(lesson__course=course).exists():
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Module membership locks after learning progress begins.")
        form.save()
        return redirect("faculty",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Edit "+kind})

@login_required
@transaction.atomic
def question(request,pk,item=0):
    quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=pk,course__instructor=request.user)
    if quiz.published:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Unpublish the quiz before editing questions.")
    if quiz.attempt_set.exists() or quiz.quizsession_set.exists():
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Questions are locked after attempts.")
    obj=get_object_or_404(Question,pk=item,quiz=quiz) if item else Question(quiz=quiz)
    form=QuestionForm(request.POST if request.method=="POST" else None,instance=obj)
    if request.method=="POST" and form.is_valid():
        form.save()
        return redirect("faculty",pk=quiz.course_id)
    return render(request,"form.html",{"form":form,"heading":"Edit question"})
