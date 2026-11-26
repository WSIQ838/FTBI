import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404,render,redirect
from .models import Course
from .course_package import export_course,import_course


@login_required
def export_package(request,pk):
    course=get_object_or_404(Course,pk=pk,instructor=request.user)
    response=JsonResponse(export_course(course))
    response["Content-Disposition"]=f'attachment; filename="course-{pk}.json"'
    response["Cache-Control"]="private, no-store"
    return response


class PackageForm(forms.Form):
    shift_days=forms.IntegerField(min_value=-365,max_value=365,initial=0,required=False,help_text="Shift assignment/quiz deadlines and calendar dates by this many days.")
    file=forms.FileField(help_text="FTBI course JSON, at most 2 MB. Student records are never imported.")
    def clean_file(self):
        file=self.cleaned_data["file"]
        if file.size>2*1024*1024: raise forms.ValidationError("Package exceeds 2 MB.")
        try: self.package=json.loads(file.read(2*1024*1024+1))
        except (ValueError,UnicodeError,RecursionError): raise forms.ValidationError("Upload valid UTF-8 JSON.")
        return file


@login_required
def import_package(request,pk):
    course=get_object_or_404(Course,pk=pk,instructor=request.user)
    form=PackageForm(request.POST if request.method=="POST" else None,request.FILES if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        try:
            import_course(course,form.package,request.user,shift_days=form.cleaned_data["shift_days"] or 0)
            return redirect("faculty",pk=pk)
        except (ValidationError,ValueError,TypeError,KeyError,IntegrityError,RecursionError):
            form.add_error("file","Invalid package or nonempty target. Nothing was imported. Check fields, references, rubric points and prerequisite cycles.")
    return render(request,"package_import.html",{"form":form,"course":course})
