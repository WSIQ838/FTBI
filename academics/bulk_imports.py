import csv
import hashlib
import json
from datetime import date
from io import StringIO
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Course,Program,Term,Department
from .registrar import StudentProfile

HEADERS={"students":["username","student_number","program_id","admitted_on","status"],"courses":["code","title","department_id","term_id","section","credits","instructor_username","syllabus"]}

def rows_digest(rows): return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def parse_csv(kind,data):
    if kind not in HEADERS or not data or len(data)>2*1024*1024: raise ValidationError("Upload a nonempty UTF-8 CSV up to 2 MB.")
    try:
        reader=csv.DictReader(StringIO(data.decode("utf-8-sig")),strict=True)
        if reader.fieldnames!=HEADERS[kind]: raise ValidationError("Required columns, in order: "+", ".join(HEADERS[kind]))
        rows=[]
        for line,row in enumerate(reader,2):
            if len(rows)>=1000 or None in row or any(v is None for v in row.values()): raise ValidationError("Use at most 1000 rows with the exact required columns.")
            rows.append({k:v.strip() for k,v in row.items()})
        if not rows: raise ValidationError("No data rows were found.")
    except (UnicodeError,csv.Error): raise ValidationError("Invalid UTF-8 CSV.")
    validate_rows(kind,rows)
    return rows

def validate_rows(kind,rows):
    records=[]; identities=set(); numbers=set()
    for index,row in enumerate(rows,2):
        try:
            if set(row)!=set(HEADERS[kind]): raise ValidationError("Unexpected columns.")
            if kind=="students":
                user=get_user_model().objects.get(username=row["username"],is_active=True,is_staff=False,is_superuser=False)
                key=user.pk
                if row["student_number"] in numbers: raise ValidationError("Duplicate student number in this file.")
                numbers.add(row["student_number"])
                record=StudentProfile(user=user,student_number=row["student_number"],program=Program.objects.get(pk=int(row["program_id"])),admitted_on=date.fromisoformat(row["admitted_on"]),status=row["status"])
            else:
                teacher=get_user_model().objects.get(username=row["instructor_username"],is_active=True)
                term=Term.objects.get(pk=int(row["term_id"]))
                key=(row["code"],term.pk,row["section"])
                record=Course(code=row["code"],title=row["title"],department=Department.objects.get(pk=int(row["department_id"])),term=term,section=row["section"],credits=int(row["credits"]),instructor=teacher,syllabus=row["syllabus"],published=False)
            if key in identities: raise ValidationError("Duplicate record in this file.")
            identities.add(key)
            record.full_clean()
            records.append(record)
        except (ValueError,TypeError,KeyError,Program.DoesNotExist,Department.DoesNotExist,Term.DoesNotExist,get_user_model().DoesNotExist):
            raise ValidationError(f"Row {index}: invalid value or missing eligible related record.")
        except ValidationError as error:
            raise ValidationError(f"Row {index}: "+"; ".join(error.messages))
    return records
