#!/bin/sh
set -eu
export DJANGO_DEBUG=1
python manage.py check
python manage.py makemigrations academics
python manage.py migrate
python manage.py test
