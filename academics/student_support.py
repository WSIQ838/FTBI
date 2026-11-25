from django.conf import settings
from django.db import models
from django.db.models import Q
from .registrar import StudentProfile
from .advising import AdvisorAssignment
from .models import Course
from .student_records import AcademicStanding

class AdvisorSlot(models.Model):
    advisor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    starts=models.DateTimeField()
    ends=models.DateTimeField()
    location=models.CharField(max_length=300)
    active=models.BooleanField(default=True)

class AdvisorBooking(models.Model):
    slot=models.ForeignKey(AdvisorSlot,on_delete=models.PROTECT,related_name="bookings")
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    status=models.CharField(max_length=12,default="booked",choices=[("booked","Booked"),("cancelled","Cancelled"),("completed","Completed")])
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["slot"],condition=Q(status="booked"),name="one_current_advisor_booking")]

class SupportCase(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    advisor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    subject=models.CharField(max_length=200)
    description=models.TextField(max_length=4000)
    category=models.CharField(max_length=16,choices=[(x,x.title()) for x in ["academic","financial","accessibility","general"]])
    status=models.CharField(max_length=12,default="open",choices=[("open","Open"),("working","In progress"),("resolved","Resolved")])
    created=models.DateTimeField(auto_now_add=True)

class SupportNote(models.Model):
    case=models.ForeignKey(SupportCase,on_delete=models.PROTECT,related_name="notes")
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    body=models.TextField(max_length=4000)
    shared=models.BooleanField(default=False)
    created=models.DateTimeField(auto_now_add=True)

class SuccessPlan(models.Model):
    case=models.ForeignKey(SupportCase,on_delete=models.PROTECT,related_name="plans")
    goals=models.TextField(max_length=4000)
    actions=models.TextField(max_length=4000)
    review_on=models.DateField()
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)

class StudentIntervention(models.Model):
    case=models.ForeignKey(SupportCase,on_delete=models.PROTECT,related_name="interventions")
    action=models.TextField(max_length=4000)
    outcome=models.TextField(max_length=4000,blank=True)
    follow_up=models.DateField()
    completed=models.BooleanField(default=False)
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created=models.DateTimeField(auto_now_add=True)

class AtRiskAlert(models.Model):
    standing=models.ForeignKey(AcademicStanding,on_delete=models.PROTECT)
    advisor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    acknowledged=models.DateTimeField(null=True)
    created=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["standing","advisor"],name="unique_standing_advisor_alert")]

class StudentAccommodation(models.Model):
    student=models.ForeignKey(StudentProfile,on_delete=models.PROTECT)
    course=models.ForeignKey(Course,on_delete=models.PROTECT)
    instructions=models.TextField(max_length=4000,help_text="Approved functional adjustments only; do not include diagnoses or medical evidence.")
    starts=models.DateField()
    ends=models.DateField()
    status=models.CharField(max_length=12,default="draft",choices=[("draft","Draft"),("approved","Approved"),("revoked","Revoked")])
    approval_reference=models.CharField(max_length=200)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="accommodations_created")
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,related_name="accommodations_reviewed")
    reviewed_at=models.DateTimeField(null=True)

def advising_students(user):
    if not user.has_perm("academics.view_advisorassignment"): return StudentProfile.objects.none()
    return StudentProfile.objects.filter(advisor_assignments__advisor=user,advisor_assignments__active=True)

def support_cases(user):
    return SupportCase.objects.filter(Q(student__user=user)|Q(advisor=user,student__in=advising_students(user))).distinct()
