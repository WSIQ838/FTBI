from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import HttpResponseForbidden
from .models import Course, Assignment, Submission
from .forms import SubmissionForm, GradeForm
from django.db import transaction
from .assessment_policy import submission_open, archive_submission
from .operations import AuditEvent

def visible_courses(user):
    return Course.objects.filter(Q(instructor=user) | Q(published=True, enrollments__student=user, enrollments__active=True)).distinct()

@login_required
def dashboard(request):
    preference=getattr(request,"portal_preference",None)
    order={"code":"code","title":"title","term":"-term__starts"}.get(getattr(preference,"course_order","code"),"code")
    return render(request, "dashboard.html", {"courses":visible_courses(request.user).order_by(order,"pk")})

@login_required
def course(request, pk):
    obj = get_object_or_404(visible_courses(request.user), pk=pk)
    teaching = obj.instructor_id == request.user.pk
    submissions = Submission.objects.filter(assignment__course=obj)
    if not teaching:
        submissions = submissions.filter(student=request.user)
    from .learning import module_open,LessonCompletion
    completed=set(LessonCompletion.objects.filter(student=request.user,lesson__course=obj).values_list("lesson_id",flat=True))
    lessons=[(lesson,teaching or module_open(lesson.module,request.user),lesson.pk in completed) for lesson in obj.lessons.select_related("module")]
    return render(request, "course.html", {"course":obj,"lessons":lessons,"teaching":teaching,"submissions":submissions.select_related("assignment","student")})

@login_required
@transaction.atomic
def submit(request, pk):
    obj = get_object_or_404(Assignment.objects.select_for_update(), pk=pk, course__published=True, course__enrollments__student=request.user, course__enrollments__active=True)
    existing = Submission.objects.filter(assignment=obj, student=request.user).first()
    if not submission_open(obj, existing):
        return HttpResponseForbidden("Submission is closed.")
    if request.method == "POST" and existing:
        # The form mutates its instance during validation; snapshot the stored row.
        previous = Submission.objects.get(pk=existing.pk)
    form = SubmissionForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        if existing:
            archive_submission(previous)
        record = form.save(commit=False)
        record.grade = None
        record.feedback = ""
        record.rubric_scores = {}
        record.assignment = obj
        record.student = request.user
        record.save()
        return redirect("course", pk=obj.course_id)
    return render(request,"form.html",{"form":form,"heading":obj.title})

@login_required
@transaction.atomic
def grade(request, pk):
    obj = get_object_or_404(Submission, pk=pk, assignment__course__instructor=request.user)
    Assignment.objects.select_for_update().get(pk=obj.assignment_id)
    obj.refresh_from_db()
    form = GradeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user, action="submission_graded", target=str(obj.pk))
        return redirect("course", pk=obj.assignment.course_id)
    return render(request,"form.html",{"form":form,"heading":"Grade submission"})
