from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404,render
from .models import Course,Enrollment
from .views import visible_courses
from .gradebook import current_grade

@login_required
def gradebook(request,pk):
    course=get_object_or_404(visible_courses(request.user),pk=pk)
    if course.instructor_id==request.user.pk:
        students=[e.student for e in Enrollment.objects.filter(course=course,active=True).select_related("student")]
    else:
        students=[request.user]
    return render(request,"gradebook.html",{"course":course,"rows":[(s,current_grade(course,s)) for s in students]})
