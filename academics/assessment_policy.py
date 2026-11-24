"""Assignment policies and immutable snapshots of superseded coursework."""
from datetime import timedelta
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .models import Assignment, Submission


class AssignmentPolicy(models.Model):
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE, related_name="policy")
    max_submissions = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    allow_graded_resubmission = models.BooleanField(default=False)
    late_hours = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(8760)])


class RubricCriterion(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="rubric")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    points = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(1000)])
    class Meta:
        ordering = ["pk"]


class SubmissionRevision(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="revisions")
    body = models.TextField()
    submitted_at = models.DateTimeField()
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    feedback = models.TextField(blank=True)
    rubric_scores = models.JSONField(default=dict)
    attachment_name = models.CharField(max_length=200, blank=True)
    attachment_data = models.BinaryField(null=True)
    archived_at = models.DateTimeField(auto_now_add=True)


def submission_open(assignment, existing=None, *, attachment=False):
    policy = AssignmentPolicy.objects.filter(assignment=assignment).first()
    deadline = assignment.due + timedelta(hours=policy.late_hours if policy else 0)
    if timezone.now() > deadline:
        return False
    if existing:
        if existing.grade is not None:
            if attachment or not policy or not policy.allow_graded_resubmission:
                return False
        if not attachment and policy and existing.revisions.count() + 1 >= policy.max_submissions:
            return False
    return True


def archive_submission(submission):
    from .attachments import SubmissionAttachment
    file = SubmissionAttachment.objects.filter(submission=submission).first()
    SubmissionRevision.objects.create(
        submission=submission, body=submission.body, submitted_at=submission.submitted_at,
        grade=submission.grade, feedback=submission.feedback, rubric_scores=submission.rubric_scores,
        attachment_name=file.original_name if file else "", attachment_data=bytes(file.data) if file else None,
    )
    if file:
        file.delete()
