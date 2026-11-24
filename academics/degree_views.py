from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_POST
from .registrar import StudentProfile
from .services import FinalGrade
from .degree import GraduationApplication

def audit(profile):
    grades=FinalGrade.objects.filter(student=profile,released=True,credits_earned__gt=0).select_related("course")
    credits={}
    for grade in grades:
        code=grade.course.code
        credits[code]=max(credits.get(code,0),grade.credits_earned)
    requirements=[(r,r.course_code in credits) for r in profile.program.requirements.all()]
    total=sum(credits.values())
    return {"requirements":requirements,"total":total,"eligible":bool(requirements) and all(done for _,done in requirements) and total>=profile.program.required_credits}

@login_required
def degree(request):
    profile=get_object_or_404(StudentProfile,user=request.user)
    return render(request,"degree.html",{"profile":profile,"audit":audit(profile),"application":GraduationApplication.objects.filter(student=profile).first()})

@login_required
@require_POST
def graduate(request):
    profile=get_object_or_404(StudentProfile,user=request.user,status="active")
    if audit(profile)["eligible"]:
        GraduationApplication.objects.get_or_create(student=profile)
    return redirect("degree")
