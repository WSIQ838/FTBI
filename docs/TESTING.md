# Testing FTBI
With dependencies installed and DJANGO_DEBUG=1 in a development environment, run:
    python manage.py makemigrations academics
    python manage.py migrate
    python manage.py check
    python manage.py test
Tests cover basic course authorization, student submissions, instructor grading, registrar records and registration restrictions. These tests are source only until actually executed. Use PostgreSQL and concurrent transaction tests before deploying registration. Never use real student data in test fixtures.
