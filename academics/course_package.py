"""Versioned course-content exchange. No student or institutional identity data."""
from datetime import timedelta,datetime
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.db import transaction
from .models import Course,Lesson,Assignment
from .learning import LearningModule,CompletionPolicy
from .assessment_policy import AssignmentPolicy,RubricCriterion
from .gradebook import GradeCategory,AssignmentWeight
from .quizzes import Quiz,Question
from .timing import QuizPolicy
from .operations import AuditEvent
from .services import Announcement,CalendarEvent
from .discussions import Discussion

QUESTION_FIELDS=["kind","prompt","points","option_a","option_b","option_c","option_d","correct","answer_key"]
ASSIGNMENT_POLICY_FIELDS=["max_submissions","allow_graded_resubmission","late_hours"]
QUIZ_POLICY_FIELDS=["minutes","shuffle","max_attempts","select_count","attempt_rule"]


def fields(obj,names): return {name:getattr(obj,name) for name in names}


def export_course(course):
    modules=list(course.modules.all()); module_indices={m.pk:i for i,m in enumerate(modules)}
    categories=list(course.grade_categories.all()); category_indices={c.pk:i for i,c in enumerate(categories)}
    assignments=[]
    for a in course.assignments.all():
        policy=AssignmentPolicy.objects.filter(assignment=a).first()
        weight=AssignmentWeight.objects.filter(assignment=a).first()
        assignments.append({**fields(a,["title","instructions","due"]),"policy":fields(policy,ASSIGNMENT_POLICY_FIELDS) if policy else None,"rubric":[fields(r,["title","description","points"]) for r in a.rubric.all()],"weight":{"category":category_indices[weight.category_id],"points":weight.points} if weight else None})
    quizzes=[]
    for q in course.quiz_set.all():
        policy=QuizPolicy.objects.filter(quiz=q).first()
        quizzes.append({**fields(q,["title","closes","results_released"]),"questions":[fields(item,QUESTION_FIELDS) for item in q.questions.all()],"policy":fields(policy,QUIZ_POLICY_FIELDS) if policy else None})
    completion=CompletionPolicy.objects.filter(course=course).first()
    return {"format":"ftbi-course","version":2,"announcements":[fields(a,["title","body"]) for a in Announcement.objects.filter(course=course).order_by("pk")],"calendar_events":[fields(e,["title","starts","ends"]) for e in CalendarEvent.objects.filter(course=course).order_by("pk")],"discussion_prompts":[fields(d,["title","prompt"]) for d in course.discussions.filter(author=course.instructor).order_by("pk")],"syllabus":course.syllabus,"modules":[{**fields(m,["title","position"]),"prerequisites":[module_indices[p.pk] for p in m.prerequisites.all()]} for m in modules],"lessons":[{**fields(lesson,["title","body","position","video_url"]),"module":module_indices.get(lesson.module_id)} for lesson in course.lessons.all()],"categories":[fields(c,["name","weight"]) for c in categories],"assignments":assignments,"quizzes":quizzes,"completion_policy":{"minimum_score":completion.minimum_score} if completion else None}


def record(data,allowed,required=None):
    if not isinstance(data,dict) or set(data)-set(allowed) or set(required if required is not None else allowed)-set(data):
        raise ValidationError("Invalid course package fields.")
    return data


def items(data):
    if not isinstance(data,list) or len(data)>500: raise ValidationError("Package lists are limited to 500 items.")
    return data


def create(model,**values):
    obj=model(**values); obj.full_clean(); obj.save(); return obj


def indexed(values,index):
    if type(index) is not int or not 0<=index<len(values): raise ValidationError("Invalid package reference.")
    return values[index]


def empty_target(target):
    return not (target.published or target.lessons.exists() or target.assignments.exists() or target.modules.exists() or target.quiz_set.exists() or target.grade_categories.exists() or CompletionPolicy.objects.filter(course=target).exists() or Announcement.objects.filter(course=target).exists() or CalendarEvent.objects.filter(course=target).exists() or target.discussions.exists())


def shifted_datetime(value,days):
    parsed=parse_datetime(value) if isinstance(value,str) else value
    if not isinstance(parsed,datetime) or timezone.is_naive(parsed): raise ValidationError("Package dates must include an explicit timezone offset.")
    try: return parsed+timedelta(days=days)
    except OverflowError: raise ValidationError("Shifted package date is outside the supported range.")


@transaction.atomic
def import_course(target,data,actor,shift_days=0):
    def complexity(value,depth=0):
        if depth>12: raise ValidationError("Course package nesting is too deep.")
        children=value.values() if isinstance(value,dict) else value if isinstance(value,list) else []
        return 1+sum(complexity(child,depth+1) for child in children)
    if type(shift_days) is not int or not -365<=shift_days<=365: raise ValidationError("Date shift must be an integer between -365 and 365 days.")
    if complexity(data)>12000: raise ValidationError("Course package contains too many entries.")
    target=Course.objects.select_for_update().get(pk=target.pk,instructor=actor)
    if not empty_target(target):
        raise ValidationError("Import requires an empty unpublished target course.")
    if not isinstance(data,dict): raise ValidationError("Invalid package object.")
    extra=["announcements","calendar_events","discussion_prompts"] if data.get("version")==2 else []
    record(data,["format","version","syllabus","modules","lessons","categories","assignments","quizzes","completion_policy"]+extra)
    if data["format"]!="ftbi-course" or type(data["version"]) is not int or data["version"] not in {1,2} or not isinstance(data["syllabus"],str):
        raise ValidationError("Unsupported course package format.")
    modules=[]; graph=[]
    for m in items(data["modules"]):
        record(m,["title","position","prerequisites"])
        modules.append(create(LearningModule,course=target,title=m["title"],position=m["position"]))
        graph.append(items(m["prerequisites"]))
    visited=set()
    def visit(index,path):
        indexed(modules,index)
        if index in path: raise ValidationError("Module prerequisites cannot form a cycle.")
        if index in visited: return
        for prerequisite in graph[index]: visit(prerequisite,path|{index})
        visited.add(index)
    for i,module in enumerate(modules):
        visit(i,set()); module.prerequisites.set([indexed(modules,index) for index in graph[i]])
    for lesson in items(data["lessons"]):
        record(lesson,["title","body","position","video_url","module"])
        values={k:lesson[k] for k in ["title","body","position","video_url"]}
        create(Lesson,course=target,module=indexed(modules,lesson["module"]) if lesson["module"] is not None else None,**values)
    categories=[create(GradeCategory,course=target,**record(c,["name","weight"])) for c in items(data["categories"])]
    for a in items(data["assignments"]):
        record(a,["title","instructions","due","policy","rubric","weight"])
        assignment=create(Assignment,course=target,title=a["title"],instructions=a["instructions"],due=shifted_datetime(a["due"],shift_days))
        if a["policy"] is not None: create(AssignmentPolicy,assignment=assignment,**record(a["policy"],ASSIGNMENT_POLICY_FIELDS))
        for criterion in items(a["rubric"]): create(RubricCriterion,assignment=assignment,**record(criterion,["title","description","points"]))
        if a["weight"] is not None:
            weight=record(a["weight"],["category","points"])
            create(AssignmentWeight,assignment=assignment,category=indexed(categories,weight["category"]),points=weight["points"])
    for q in items(data["quizzes"]):
        record(q,["title","closes","results_released","questions","policy"])
        quiz=create(Quiz,course=target,published=False,title=q["title"],closes=shifted_datetime(q["closes"],shift_days),results_released=q["results_released"])
        for question in items(q["questions"]): create(Question,quiz=quiz,**record(question,QUESTION_FIELDS))
        if q["policy"] is not None:
            policy=create(QuizPolicy,quiz=quiz,**record(q["policy"],QUIZ_POLICY_FIELDS))
            if policy.select_count>quiz.questions.count(): raise ValidationError("Question pool is too small.")
    if data["completion_policy"] is not None:
        create(CompletionPolicy,course=target,enabled=False,**record(data["completion_policy"],["minimum_score"]))
    if data["version"]==2:
        for announcement in items(data["announcements"]):
            create(Announcement,course=target,published=False,**record(announcement,["title","body"]))
        for calendar_event in items(data["calendar_events"]):
            record(calendar_event,["title","starts","ends"])
            starts=shifted_datetime(calendar_event["starts"],shift_days);ends=shifted_datetime(calendar_event["ends"],shift_days)
            if ends<=starts: raise ValidationError("Calendar events must end after starting.")
            create(CalendarEvent,course=target,published=False,title=calendar_event["title"],starts=starts,ends=ends)
        for prompt in items(data["discussion_prompts"]):
            create(Discussion,course=target,author=actor,closed=True,**record(prompt,["title","prompt"]))
    target.syllabus=data["syllabus"]; target.save(update_fields=["syllabus"])
    AuditEvent.objects.create(actor=actor,action="course_package_imported",target=str(target.pk))
