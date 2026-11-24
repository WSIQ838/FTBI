from io import BytesIO
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.http import HttpResponseForbidden,HttpResponse,Http404
from django.views.decorators.http import require_POST
from reportlab.pdfgen import canvas
from .models import Course,Lesson,Enrollment
from .learning import LearningModule,LessonCompletion,CompletionPolicy,CourseCertificate,module_open,course_complete
from .operations import AuditEvent
from .views import visible_courses


class ModuleForm(forms.ModelForm):
    class Meta:
        model=LearningModule
        fields=["title","position","prerequisites"]
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["prerequisites"].queryset=LearningModule.objects.filter(course=self.instance.course).exclude(pk=self.instance.pk)
    def clean_prerequisites(self):
        prerequisites=self.cleaned_data["prerequisites"]
        def contains(module,target,seen):
            if module.pk==target: return True
            if module.pk in seen: return False
            seen.add(module.pk)
            return any(contains(p,target,seen) for p in module.prerequisites.all())
        if self.instance.pk and any(contains(p,self.instance.pk,set()) for p in prerequisites):
            raise forms.ValidationError("Module prerequisites cannot form a cycle.")
        return prerequisites


@login_required
@transaction.atomic
def module_editor(request,pk,item=0):
    course=get_object_or_404(Course.objects.select_for_update(),pk=pk,instructor=request.user)
    module=get_object_or_404(LearningModule,pk=item,course=course) if item else LearningModule(course=course)
    if LessonCompletion.objects.filter(lesson__course=course).exists():
        return HttpResponseForbidden("Module structure locks after learning progress begins.")
    form=ModuleForm(request.POST if request.method=="POST" else None,instance=module)
    if request.method=="POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user,action="learning_module_updated",target=str(course.pk))
        return redirect("faculty",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Learning module"})


@login_required
@require_POST
@transaction.atomic
def complete_lesson(request,pk):
    lesson=get_object_or_404(Lesson,pk=pk,course__published=True,course__enrollments__student=request.user,course__enrollments__active=True)
    Course.objects.select_for_update().get(pk=lesson.course_id)
    if not module_open(lesson.module,request.user): return HttpResponseForbidden("Complete prerequisite modules first.")
    LessonCompletion.objects.get_or_create(lesson=lesson,student=request.user)
    return redirect("course",pk=lesson.course_id)


@login_required
def completion_policy(request,pk):
    course=get_object_or_404(Course,pk=pk,instructor=request.user)
    class PolicyForm(forms.ModelForm):
        class Meta:
            model=CompletionPolicy
            fields=["enabled","minimum_score"]
    policy=CompletionPolicy.objects.filter(course=course).first() or CompletionPolicy(course=course)
    form=PolicyForm(request.POST if request.method=="POST" else None,instance=policy)
    if request.method=="POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user,action="completion_policy_updated",target=str(pk))
        return redirect("faculty",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Course completion certificate policy"})


@login_required
@require_POST
@transaction.atomic
def issue_certificate(request,pk):
    course=get_object_or_404(Course.objects.select_for_update(),pk=pk,published=True,enrollments__student=request.user,enrollments__active=True)
    existing=CourseCertificate.objects.filter(course=course,student=request.user).first()
    if existing: return redirect("course_certificate",identifier=existing.identifier)
    if not course_complete(course,request.user): return HttpResponseForbidden("Course completion requirements are not met.")
    certificate=CourseCertificate.objects.create(course=course,student=request.user,snapshot={"student":request.user.get_full_name() or request.user.username,"course":course.title,"code":course.code,"term":course.term.name,"minimum_score":str(course.completion_policy.minimum_score)})
    AuditEvent.objects.create(actor=request.user,action="course_certificate_issued",target=str(certificate.identifier))
    return redirect("course_certificate",identifier=certificate.identifier)


@login_required
def certificate_pdf(request,identifier):
    certificate=get_object_or_404(CourseCertificate.objects.select_related("course"),identifier=identifier)
    if request.user.pk not in (certificate.student_id,certificate.course.instructor_id): raise Http404()
    buffer=BytesIO(); pdf=canvas.Canvas(buffer)
    pdf.setTitle("Course completion certificate")
    data=certificate.snapshot
    for y,text in [(780,"Course completion certificate"),(740,data["student"]),(710,data["course"]),(680,f'{data["code"]} - {data["term"]}'),(650,f"Issued: {certificate.issued.date()}"),(620,str(certificate.identifier))]:
        pdf.drawString(45,y,text[:120])
    pdf.save()
    response=HttpResponse(buffer.getvalue(),content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="course-certificate-{identifier}.pdf"'
    response["Cache-Control"]="private, no-store"
    return response


@login_required
def attendance_analytics(request,pk):
    from collections import Counter
    from .services import Attendance
    course=get_object_or_404(visible_courses(request.user),pk=pk)
    students=[e.student for e in Enrollment.objects.filter(course=course,active=True).select_related("student")] if course.instructor_id==request.user.pk else [request.user]
    rows=[]
    for student in students:
        counts=Counter(Attendance.objects.filter(course=course,student__user=student).values_list("status",flat=True))
        denominator=counts["present"]+counts["late"]+counts["absent"]
        rate=round(100*(counts["present"]+counts["late"])/denominator,1) if denominator else None
        rows.append((student,dict(counts),rate))
    return render(request,"attendance_analytics.html",{"course":course,"rows":rows})
