# FTBI development setup
Requires Python 3.10+.
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1
python manage.py makemigrations academics
python manage.py migrate
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```
Windows PowerShell: activate with .venv\Scripts\Activate.ps1 and use $env:DJANGO_DEBUG="1".
Visit http://127.0.0.1:8000/admin/ to create users, departments, terms, courses, enrollments, lessons and assignments. Assign a course instructor, publish the course, and enroll a student. Sign in at /login/ with the student or instructor account. Professors can grade submissions from their course view. Course authoring currently requires admin access; do not grant broad admin permissions to ordinary faculty.
Development only: SQLite and Django runserver. Production requires a supported WSGI server, PostgreSQL, static serving, HTTPS, a unique DJANGO_SECRET_KEY and appropriate DJANGO_ALLOWED_HOSTS, plus security review. Initial migrations are generated locally and should be reviewed and committed before deployment.
