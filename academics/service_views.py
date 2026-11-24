from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from .views import visible_courses
from .registrar import StudentProfile
from .services import FinalGrade, Attendance, Announcement, CalendarEvent, LedgerEntry, Practicum, LibraryResource

@login_required
def student_services(request):
    profile=StudentProfile.objects.filter(user=request.user).select_related("program").first()
    courses=visible_courses(request.user)
    scope=Q(course__isnull=True)|Q(course__in=courses)
    context={"profile":profile,"announcements":Announcement.objects.filter(scope,published=True).order_by("-created"),"events":CalendarEvent.objects.filter(scope,published=True).order_by("starts"),"resources":LibraryResource.objects.filter(published=True)}
    if profile:
        grades=FinalGrade.objects.filter(student=profile,released=True).select_related("course","course__term")
        graded=[g for g in grades if g.quality_points is not None]
        attempted=sum(g.course.credits for g in graded)
        context.update(grades=grades,earned=sum(g.credits_earned for g in grades),gpa=round(sum((g.quality_points*g.course.credits for g in graded),Decimal(0))/attempted,2) if attempted else None,attendance=Attendance.objects.filter(student=profile).select_related("course"),ledger=LedgerEntry.objects.filter(student=profile,released=True),practicum=Practicum.objects.filter(student=profile,approved=True))
        context["balance"]=sum((e.amount for e in context["ledger"]),Decimal(0))
        context["hours"]=sum((p.hours for p in context["practicum"]),Decimal(0))
    return render(request,"services.html",context)
