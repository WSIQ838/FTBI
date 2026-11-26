from django.contrib import admin
from .models import Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission
# Only superusers have access by default. Delegate model permissions carefully.
for model in [Department, Program, Term, Course, Enrollment, Lesson, Assignment, Submission]:
    admin.site.register(model)
admin.site.site_header = "FTBI Administration"

from .registrar import StudentProfile, RegistrationWindow, Application
for model in [StudentProfile, RegistrationWindow, Application]:
    admin.site.register(model)

from .services import FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource
for model in [FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, AdvisingNote, Practicum, LearningOutcome, LibraryResource]:
    admin.site.register(model)

from .quizzes import Quiz, Question, Attempt
admin.site.register(Quiz)

class AssessmentRecordAdmin(admin.ModelAdmin):
    """Use the locked, scoped authoring/grading routes for assessment writes."""
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

admin.site.register(Question, AssessmentRecordAdmin)
admin.site.register(Attempt, AssessmentRecordAdmin)

from .degree import DegreeRequirement, GraduationApplication
admin.site.register(DegreeRequirement)
admin.site.register(GraduationApplication)

from .gradebook import GradeCategory, AssignmentWeight
admin.site.register(GradeCategory)
admin.site.register(AssignmentWeight)

from .operations import FinancialAidAward, TransferCredit, TranscriptRequest, Message, AuditEvent
for model in [FinancialAidAward, TransferCredit, TranscriptRequest]:
    admin.site.register(model)
@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display=("created","actor","action","target")
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

from .transcripts import IssuedTranscript
@admin.register(IssuedTranscript)
class IssuedTranscriptAdmin(admin.ModelAdmin):
    list_display=('identifier','issued_at','issued_by')
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

from .payments import PaymentRequest
@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display=("student","amount","status","created")
    def has_change_permission(self,request,obj=None):
        return False
    def has_delete_permission(self,request,obj=None): return False
    def has_add_permission(self,request): return False
    def get_readonly_fields(self,request,obj=None):
        return ("student","amount","reference","created")

from .discussions import Discussion, DiscussionReply
admin.site.register(Discussion)
admin.site.register(DiscussionReply)

from .prerequisites import Prerequisite, WaitlistEntry
admin.site.register(Prerequisite)
admin.site.register(WaitlistEntry)

from .evaluations import EvaluationWindow, CourseEvaluation
admin.site.register(EvaluationWindow)
admin.site.register(CourseEvaluation)

from .timing import QuizPolicy
admin.site.register(QuizPolicy, AssessmentRecordAdmin)

from .identity_models import IdentityLink
admin.site.register(IdentityLink)

from .advising import AdvisorAssignment
from .diplomas import IssuedDiploma
admin.site.register(AdvisorAssignment)
@admin.register(IssuedDiploma)
class IssuedDiplomaAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

from .exam_extensions import ExamAccommodation
admin.site.register(ExamAccommodation)

from .billing import TuitionSchedule,Invoice,PaymentAllocation,PaymentPlan,Installment
admin.site.register(TuitionSchedule)
for model in [Invoice,PaymentAllocation,PaymentPlan,Installment]:
    admin.site.register(model,AssessmentRecordAdmin)

admin.site.unregister(LedgerEntry)
@admin.register(LedgerEntry)
class LedgerAdmin(admin.ModelAdmin):
    def has_change_permission(self,request,obj=None):
        if obj and (hasattr(obj,"invoice") or hasattr(obj,"payment_record") or hasattr(obj,"payment_adjustment")): return False
        return super().has_change_permission(request,obj)
    def has_delete_permission(self,request,obj=None): return False

from .account_security import AccountSecurity,AccountSession,SecurityIncident,AccountControlEvent
from .notification_models import DurableNotification
for model in [AccountSecurity,AccountSession,AccountControlEvent]:
    admin.site.register(model,AssessmentRecordAdmin)
@admin.register(DurableNotification)
class NotificationAdmin(AssessmentRecordAdmin):
    list_display=("user","category","created","email_status","email_attempts")
    list_filter=("email_status","category")
    actions=["retry_failed"]
    def has_retry_permission(self,request): return request.user.has_perm("academics.change_durablenotification")
    @admin.action(description="Retry failed email delivery",permissions=["retry"])
    def retry_failed(self,request,queryset):
        from django.utils import timezone
        count=queryset.filter(email_status="failed").update(email_status="pending",email_attempts=0,next_attempt=timezone.now())
        AuditEvent.objects.create(actor=request.user,action="notification_retry_requested",target=str(count))
@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display=("title","severity","status","owner","updated")
    list_filter=("severity","status")
    def has_delete_permission(self,request,obj=None): return False

from .ai_governance import AIConfiguration,AIUsage,KnowledgeDocument
admin.site.register(AIConfiguration,AssessmentRecordAdmin)
admin.site.register(AIUsage,AssessmentRecordAdmin)
@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display=("title","audience","approved","updated")
    list_filter=("audience","approved")
    search_fields=("title","body")

from .student_records import WithdrawalWindow,WithdrawalRequest,GradingScale,StandingPolicy,AcademicStanding,EmergencyContact,StudentStatusRecord,EnrollmentVerification
for model in [WithdrawalWindow,GradingScale,StandingPolicy]: admin.site.register(model)
for model in [WithdrawalRequest,AcademicStanding,StudentStatusRecord,EnrollmentVerification]: admin.site.register(model,AssessmentRecordAdmin)
admin.site.register(EmergencyContact)
admin.site.unregister(StudentProfile)
@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display=("student_number","user","program","status","registration_hold")
    def save_model(self,request,obj,form,change):
        obj._status_actor=request.user
        super().save_model(request,obj,form,change)

from .documents import PrivateDocument,StorageQuota
admin.site.register(StorageQuota)
@admin.register(PrivateDocument)
class InstitutionalDocumentAdmin(admin.ModelAdmin):
    list_display=("title","published","owner")
    fields=("title","owner","kind","published")
    readonly_fields=("title","owner","kind")
    def get_queryset(self,request): return super().get_queryset(request).filter(kind="institution")
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_change_permission(self,request,obj=None): return request.user.has_perms(["academics.change_privatedocument","academics.change_libraryresource"])

from .credentials import CredentialTemplate,CredentialArtifact,CredentialRevocation,CredentialReplacement
admin.site.register(CredentialTemplate)
for model in [CredentialArtifact,CredentialRevocation,CredentialReplacement]:
    admin.site.register(model,AssessmentRecordAdmin)

from .finance_adjustments import PaymentAdjustment,AllocationReduction,PaymentDispute,FinancialHoldPolicy,FinancialHold
admin.site.register(FinancialHoldPolicy)
for model in [PaymentAdjustment,AllocationReduction,PaymentDispute,FinancialHold]: admin.site.register(model,AssessmentRecordAdmin)
