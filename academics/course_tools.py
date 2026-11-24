from datetime import timedelta
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import modelformset_factory
from django.shortcuts import render,redirect,get_object_or_404
from django.http import HttpResponse,HttpResponseForbidden
from django.utils import timezone
from .models import Course,Lesson,Assignment,Submission
from .forms import GradeForm
from .operations import AuditEvent
from .views import visible_courses
from .services import CalendarEvent
from django.db.models import Q

@login_required
def bulk_grade(request,pk):
    assignment=get_object_or_404(Assignment,pk=pk,course__instructor=request.user)
    scope=Submission.objects.filter(assignment=assignment).order_by("pk")
    FormSet=modelformset_factory(Submission,form=GradeForm,extra=0,max_num=100,validate_max=True)
    if scope.count()>100:
        return HttpResponseForbidden("Use individual grading for more than 100 submissions.")
    with transaction.atomic():
        if request.method=="POST":
            Assignment.objects.select_for_update().get(pk=assignment.pk)
            list(scope.select_for_update())
        forms_set=FormSet(request.POST if request.method=="POST" else None,queryset=scope)
        if request.method=="POST" and forms_set.is_valid():
            if any(f.instance.pk not in set(scope.values_list("pk",flat=True)) for f in forms_set.forms):
                return HttpResponseForbidden("Invalid submission.")
            forms_set.save()
            AuditEvent.objects.create(actor=request.user,action="bulk_grading",target=str(assignment.pk))
            return redirect("faculty",pk=assignment.course_id)
    return render(request,"bulk_grade.html",{"assignment":assignment,"forms_set":forms_set})

class CopyForm(forms.Form):
    source=forms.ModelChoiceField(queryset=Course.objects.none())
    shift_days=forms.IntegerField(min_value=-365,max_value=365,initial=0)
    def __init__(self,*args,user,target,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["source"].queryset=Course.objects.filter(instructor=user).exclude(pk=target.pk)

@login_required
def copy_content(request,pk):
    target=get_object_or_404(Course,pk=pk,instructor=request.user)
    form=CopyForm(request.POST if request.method=="POST" else None,user=request.user,target=target)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            target=get_object_or_404(Course.objects.select_for_update(),pk=pk,instructor=request.user)
            if target.published or target.lessons.exists() or target.assignments.exists() or target.quiz_set.exists() or target.grade_categories.exists() or target.modules.exists() or hasattr(target,"completion_policy"):
                return HttpResponseForbidden("Target must be unpublished with no lessons, assignments, quizzes or grading categories.")
            source=form.cleaned_data["source"]
            delta=timedelta(days=form.cleaned_data["shift_days"])
            target.syllabus=source.syllabus
            target.save(update_fields=["syllabus"])
            from .learning import LearningModule,CompletionPolicy
            modules={m.pk:LearningModule.objects.create(course=target,title=m.title,position=m.position) for m in source.modules.all()}
            for original in source.modules.all():
                modules[original.pk].prerequisites.set([modules[p.pk] for p in original.prerequisites.all() if p.pk in modules])
            Lesson.objects.bulk_create([Lesson(course=target,title=x.title,body=x.body,position=x.position,module=modules.get(x.module_id),video_url=x.video_url) for x in source.lessons.all()])
            completion=CompletionPolicy.objects.filter(course=source).first()
            if completion:
                CompletionPolicy.objects.create(course=target,enabled=False,minimum_score=completion.minimum_score)
            from .assessment_policy import AssignmentPolicy, RubricCriterion
            from .gradebook import GradeCategory, AssignmentWeight
            from .quizzes import Quiz, Question
            from .timing import QuizPolicy
            categories = {c.pk: GradeCategory.objects.create(course=target, name=c.name, weight=c.weight) for c in source.grade_categories.all()}
            for original in source.assignments.all():
                copied = Assignment.objects.create(course=target,title=original.title,instructions=original.instructions,due=original.due+delta)
                policy = AssignmentPolicy.objects.filter(assignment=original).first()
                if policy:
                    AssignmentPolicy.objects.create(assignment=copied, max_submissions=policy.max_submissions, allow_graded_resubmission=policy.allow_graded_resubmission, late_hours=policy.late_hours)
                RubricCriterion.objects.bulk_create([RubricCriterion(assignment=copied,title=c.title,description=c.description,points=c.points) for c in original.rubric.all()])
                weight = AssignmentWeight.objects.filter(assignment=original).first()
                if weight and weight.category_id in categories:
                    AssignmentWeight.objects.create(assignment=copied, category=categories[weight.category_id], points=weight.points)
            for original in source.quiz_set.all():
                copied = Quiz.objects.create(course=target,title=original.title,closes=original.closes+delta,published=False,results_released=original.results_released)
                Question.objects.bulk_create([Question(quiz=copied,kind=q.kind,points=q.points,answer_key=q.answer_key,prompt=q.prompt,option_a=q.option_a,option_b=q.option_b,option_c=q.option_c,option_d=q.option_d,correct=q.correct) for q in original.questions.all()])
                policy = QuizPolicy.objects.filter(quiz=original).first()
                if policy:
                    QuizPolicy.objects.create(quiz=copied, minutes=policy.minutes, shuffle=policy.shuffle, max_attempts=policy.max_attempts,select_count=policy.select_count,attempt_rule=policy.attempt_rule)
            AuditEvent.objects.create(actor=request.user,action="course_content_copied",target=str(target.pk))
        return redirect("faculty",pk=pk)
    return render(request,"form.html",{"form":form,"heading":"Copy lessons and assignments from my course"})

@login_required
def progress(request,pk):
    course=get_object_or_404(visible_courses(request.user),pk=pk)
    assignments=course.assignments.count()
    submitted=Submission.objects.filter(student=request.user,assignment__course=course).count()
    graded=Submission.objects.filter(student=request.user,assignment__course=course,grade__isnull=False).count()
    from .learning import LessonCompletion,course_complete
    return render(request,"progress.html",{"course":course,"assignments":assignments,"submitted":submitted,"graded":graded,"lesson_count":course.lessons.count(),"completed_lessons":LessonCompletion.objects.filter(student=request.user,lesson__course=course).count(),"complete":course_complete(course,request.user)})

def escape_ical(value):
    return str(value).replace("\\","\\\\").replace("\r\n","\\n").replace("\r","\\n").replace("\n","\\n").replace(";","\\;").replace(",","\\,")

def fold_line(line):
    chunks=[]
    current=""
    for char in line:
        if len((current+char).encode("utf-8"))>75:
            chunks.append(current)
            current=" "
        current+=char
    chunks.append(current)
    return "\r\n".join(chunks)

@login_required
def calendar_export(request):
    from datetime import timezone as utc
    courses=visible_courses(request.user)
    events=CalendarEvent.objects.filter(Q(course__isnull=True)|Q(course__in=courses),published=True).order_by("starts")[:1000]
    def stamp(value): return value.astimezone(utc.utc).strftime("%Y%m%dT%H%M%SZ")
    lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//FTBI//Academic calendar//EN","CALSCALE:GREGORIAN"]
    now=stamp(timezone.now())
    for event in events:
        lines.extend(["BEGIN:VEVENT",f"UID:event-{event.pk}@ftbi",f"DTSTAMP:{now}",f"DTSTART:{stamp(event.starts)}",f"DTEND:{stamp(event.ends)}","SUMMARY:"+escape_ical(event.title),"END:VEVENT"])
    lines.append("END:VCALENDAR")
    response=HttpResponse("\r\n".join(fold_line(line) for line in lines)+"\r\n",content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"]='attachment; filename="academic-calendar.ics"'
    response["Cache-Control"]="private, no-store"
    return response
