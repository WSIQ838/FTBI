"""Read-only fingerprint of serialized application rows for disposable restore drills."""
import hashlib
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","ftbi.settings")
import django
django.setup()
from django.apps import apps
from django.core import serializers

digest=hashlib.sha256()
count=0
for model in sorted(apps.get_models(),key=lambda m:m._meta.label):
    rows=model.objects.order_by("pk")
    count+=rows.count()
    digest.update(model._meta.label.encode())
    digest.update(serializers.serialize("json",rows,sort_keys=True).encode())
print(f"{count} rows {digest.hexdigest()}")
