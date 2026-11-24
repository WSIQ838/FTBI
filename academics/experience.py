from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from .views import visible_courses
from .models import Assignment, Submission, Lesson
from .operations import Message
from .services import Announcement
from .quizzes import Quiz,Attempt

@login_required
def search(request):
    term=request.GET.get("q","").strip()[:150]
    courses=visible_courses(request.user)
    result={"query":term}
    if len(term)>=2:
        result.update(courses=courses.filter(Q(title__icontains=term)|Q(code__icontains=term))[:50],lessons=Lesson.objects.filter(course__in=courses,title__icontains=term).select_related("course")[:50],assignments=Assignment.objects.filter(course__in=courses,title__icontains=term).select_related("course")[:50])
        from .learning import module_open
        result["lessons"]=[lesson for lesson in result["lessons"] if lesson.course.instructor_id==request.user.pk or module_open(lesson.module,request.user)]
    return render(request,"search.html",result)

@login_required
def notifications(request):
    courses=visible_courses(request.user)
    enrolled=courses.filter(enrollments__student=request.user,enrollments__active=True,published=True)
    completed=Submission.objects.filter(student=request.user).values("assignment_id")
    attempted=Attempt.objects.filter(student=request.user).values("quiz_id")
    now=timezone.now()
    return render(request,"notifications.html",{
        "messages_list":Message.objects.filter(recipient=request.user,read__isnull=True).select_related("sender").order_by("-sent")[:50],
        "announcements":Announcement.objects.filter(Q(course__isnull=True)|Q(course__in=courses),published=True).order_by("-created")[:30],
        "assignments":Assignment.objects.filter(course__in=enrolled,due__gte=now).exclude(pk__in=completed).select_related("course").order_by("due")[:30],
        "quizzes":Quiz.objects.filter(course__in=enrolled,published=True,closes__gte=now).exclude(pk__in=attempted).select_related("course").order_by("closes")[:30],
    })
