from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import HttpResponseForbidden
from .models import Course, Assignment, Submission
from .forms import SubmissionForm, GradeForm

def visible_courses(user):
    return Course.objects.filter(Q(instructor=user) | Q(published=True, enrollments__student=user, enrollments__active=True)).distinct()

@login_required
def dashboard(request):
    return render(request, "dashboard.html", {"courses":visible_courses(request.user)})

@login_required
def course(request, pk):
    obj = get_object_or_404(visible_courses(request.user), pk=pk)
    teaching = obj.instructor_id == request.user.pk
    submissions = Submission.objects.filter(assignment__course=obj)
    if not teaching:
        submissions = submissions.filter(student=request.user)
    return render(request, "course.html", {"course":obj,"teaching":teaching,"submissions":submissions.select_related("assignment","student")})

@login_required
def submit(request, pk):
    obj = get_object_or_404(Assignment, pk=pk, course__published=True, course__enrollments__student=request.user, course__enrollments__active=True)
    existing = Submission.objects.filter(assignment=obj, student=request.user).first()
    if timezone.now() > obj.due or (existing and existing.grade is not None):
        return HttpResponseForbidden("Submission is closed.")
    form = SubmissionForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.assignment = obj
        record.student = request.user
        record.save()
        return redirect("course", pk=obj.course_id)
    return render(request,"form.html",{"form":form,"heading":obj.title})

@login_required
def grade(request, pk):
    obj = get_object_or_404(Submission, pk=pk, assignment__course__instructor=request.user)
    form = GradeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("course", pk=obj.assignment.course_id)
    return render(request,"form.html",{"form":form,"heading":"Grade submission"})
