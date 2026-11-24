from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import inlineformset_factory
from django.http import HttpResponseForbidden, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from .models import Assignment, Submission
from .assessment_policy import AssignmentPolicy, RubricCriterion, SubmissionRevision
from .operations import AuditEvent


class PolicyForm(forms.ModelForm):
    class Meta:
        model = AssignmentPolicy
        fields = ["max_submissions", "allow_graded_resubmission", "late_hours"]


@login_required
@transaction.atomic
def assignment_policy(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_for_update(), pk=pk, course__instructor=request.user)
    policy = AssignmentPolicy.objects.filter(assignment=assignment).first() or AssignmentPolicy(assignment=assignment)
    form = PolicyForm(request.POST if request.method == "POST" else None, instance=policy)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user, action="assignment_policy_updated", target=str(pk))
        return redirect("faculty", pk=assignment.course_id)
    return render(request, "form.html", {"form": form, "heading": "Submission policy: " + assignment.title})


@login_required
@transaction.atomic
def rubric(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_for_update(), pk=pk, course__instructor=request.user)
    if assignment.submissions.exists():
        return HttpResponseForbidden("Rubrics are locked after the first submission. Copy the assignment to revise its rubric.")
    FormSet = inlineformset_factory(Assignment, RubricCriterion, fields=["title", "description", "points"], extra=3, max_num=30, validate_max=True)
    formset = FormSet(request.POST if request.method == "POST" else None, instance=assignment)
    if request.method == "POST" and formset.is_valid():
        formset.save()
        AuditEvent.objects.create(actor=request.user, action="rubric_updated", target=str(pk))
        return redirect("faculty", pk=assignment.course_id)
    return render(request, "rubric.html", {"assignment": assignment, "formset": formset})


def authorized_submission(user, pk):
    submission = get_object_or_404(Submission.objects.select_related("assignment__course"), pk=pk)
    course = submission.assignment.course
    if user.pk != course.instructor_id and not (
        user.pk == submission.student_id and course.published
        and course.enrollments.filter(student=user, active=True).exists()
    ):
        raise Http404()
    return submission


@login_required
def submission_history(request, pk):
    submission = authorized_submission(request.user, pk)
    return render(request, "submission_history.html", {"submission": submission, "revisions": submission.revisions.order_by("-archived_at", "-pk")})


@login_required
def revision_attachment(request, pk):
    from django.utils.http import content_disposition_header
    revision = get_object_or_404(SubmissionRevision, pk=pk)
    authorized_submission(request.user, revision.submission_id)
    if revision.attachment_data is None:
        raise Http404()
    response = HttpResponse(bytes(revision.attachment_data), content_type="application/octet-stream")
    response["Content-Disposition"] = content_disposition_header(True, revision.attachment_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
