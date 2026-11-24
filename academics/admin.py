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
for model in [Quiz, Question, Attempt]:
    admin.site.register(model)

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
admin.site.register(PaymentRequest)

from .discussions import Discussion, DiscussionReply
admin.site.register(Discussion)
admin.site.register(DiscussionReply)

from .prerequisites import Prerequisite, WaitlistEntry
admin.site.register(Prerequisite)
admin.site.register(WaitlistEntry)

from .evaluations import EvaluationWindow, CourseEvaluation
admin.site.register(EvaluationWindow)
admin.site.register(CourseEvaluation)
