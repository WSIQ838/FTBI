"""Synthetic clean/EICAR checks against the real disposable CI ClamAV service."""
import base64
import os
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","ftbi.settings")
import django
django.setup()
from django.test import override_settings
from academics.scanning import scan_clean

deadline=time.monotonic()+420
while not scan_clean(b"Synthetic clean FTBI scanner probe"):
    if time.monotonic()>deadline: raise RuntimeError("Scanner did not become ready")
    time.sleep(5)
# Standard harmless antivirus test signature; never a real malicious payload.
signature=base64.b64decode("WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=")
if scan_clean(signature): raise RuntimeError("Scanner accepted the EICAR test signature")
if not scan_clean(b"Synthetic clean FTBI follow-up"): raise RuntimeError("Scanner stopped responding")
with override_settings(FTBI_CLAMAV_HOST="127.0.0.1",FTBI_CLAMAV_PORT=1):
    if scan_clean(b"Clean file during outage"): raise RuntimeError("Scanner outage was not fail-closed")
print("Real ClamAV clean, EICAR rejection, subsequent clean scan and outage rejection passed.")
