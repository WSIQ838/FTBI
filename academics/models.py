from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    def __str__(self): return self.name

class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    required_credits = models.PositiveIntegerField(default=120)
    def __str__(self): return self.name

class Term(models.Model):
    name = models.CharField(max_length=100, unique=True)
    starts = models.DateField()
    ends = models.DateField()
    def clean(self):
        if self.starts and self.ends and self.ends < self.starts:
            raise ValidationError("End date precedes start date.")
    def __str__(self): return self.name

class Course(models.Model):
    campus=models.ForeignKey("academics.Campus",on_delete=models.PROTECT,null=True,blank=True)
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    term = models.ForeignKey(Term, on_delete=models.PROTECT)
    section = models.CharField(max_length=20, default="01")
    credits = models.PositiveSmallIntegerField(default=3)
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teaching")
    syllabus = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["code","term","section"], name="unique_course_section")]
    def __str__(self): return f"{self.code} - {self.title} ({self.section})"

class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["student","course"], name="unique_enrollment")]
    def __str__(self): return f"{self.student} / {self.course}"

class Lesson(models.Model):
    module=models.ForeignKey("academics.LearningModule",on_delete=models.PROTECT,null=True,blank=True)
    video_url=models.URLField(blank=True,max_length=1000)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    body = models.TextField()
    position = models.PositiveIntegerField(default=1)
    class Meta:
        ordering = ["position","pk"]
    def __str__(self): return self.title
    def clean(self):
        from urllib.parse import urlparse
        if self.module_id and self.module.course_id!=self.course_id:
            raise ValidationError("The module must belong to this course.")
        if self.video_url:
            url=urlparse(self.video_url)
            if url.scheme!="https" or not url.hostname or url.username or url.password:
                raise ValidationError("Video URLs must use HTTPS without embedded credentials.")

class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    due = models.DateTimeField()
    def __str__(self): return self.title

class Submission(models.Model):
    rubric_scores = models.JSONField(default=dict, blank=True)
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submissions")
    body = models.TextField()
    submitted_at = models.DateTimeField(auto_now=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0),MaxValueValidator(100)])
    feedback = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment","student"], name="unique_submission")]
    def __str__(self): return f"{self.assignment} / {self.student}"

from .registrar import StudentProfile, RegistrationWindow, Application

from .services import FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource

from .quizzes import Quiz, Question, Attempt, AttemptAnswer

from .degree import DegreeRequirement, GraduationApplication

from .gradebook import GradeCategory, AssignmentWeight

from .operations import FinancialAidAward, TransferCredit, TranscriptRequest, Message, AuditEvent

from .transcripts import IssuedTranscript

from .payments import PaymentRequest

from .discussions import Discussion, DiscussionReply

from .prerequisites import Prerequisite, WaitlistEntry

from .evaluations import EvaluationWindow, CourseEvaluation

from .attachments import SubmissionAttachment

from .timing import QuizPolicy, QuizSession

from .identity_models import IdentityLink

from .advising import AdvisorAssignment
from .diplomas import IssuedDiploma

from .exam_extensions import ExamAccommodation,BankQuestion

from .recovery_models import RecoveryCode

from .assessment_policy import AssignmentPolicy, RubricCriterion, SubmissionRevision
from .billing import TuitionSchedule, Invoice, PaymentAllocation, PaymentPlan, Installment, AllocationOperation
from .learning import LearningModule, LessonCompletion, CompletionPolicy, CourseCertificate
from .notification_models import DurableNotification, NotificationPreference
from .account_security import AccountSecurity, AccountSession, SecurityIncident, AccountControlEvent
from .ai_governance import AIConfiguration, KnowledgeDocument, AIUsage
from .student_records import WithdrawalWindow,WithdrawalRequest,GradingScale,StandingPolicy,AcademicStanding,EmergencyContact,StudentStatusRecord,EnrollmentVerification
from .admissions_support import ApplicantActivation,ApplicationReviewer,ApplicationNote,AdmissionInterview
from .documents import PrivateDocument,DocumentVersion,DocumentVerification,StorageQuota
from .student_support import AdvisorSlot,AdvisorBooking,SupportCase,SupportNote,SuccessPlan,StudentIntervention,AtRiskAlert,StudentAccommodation
from .institution import InstitutionSettings,PortalPreference,ImportBatch
from .credentials import CredentialTemplate,CredentialArtifact,CredentialRevocation,CredentialReplacement

from .finance_adjustments import PaymentAdjustment,AllocationReduction,PaymentDispute,FinancialHoldPolicy,FinancialHold

from .scholarships import ScholarshipFund,ScholarshipApplication,ScholarshipAward,ScholarshipEvent

from .institutional_reporting import Campus,DeanAssignment,InstitutionalReport,ReportSnapshot,ReportReview
