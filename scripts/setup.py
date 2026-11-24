#!/usr/bin/env python3
"""Local operator wizard. Generates secrets, never overwrites an existing environment."""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--production",action="store_true")
    parser.add_argument("--domain")
    parser.add_argument("--institution",default="FTBI Academic Portal")
    parser.add_argument("--short-name",default="FTBI")
    parser.add_argument("--start",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    domain=args.domain or ("localhost" if not args.production else input("Production DNS hostname: ").strip())
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",domain):
        parser.error("Provide a valid DNS hostname")
    for value in (args.institution,args.short_name):
        if not re.fullmatch(r"[A-Za-z0-9 .,&()_-]{1,100}",value):
            parser.error("Institution name must contain only supported characters")
    env=root/".env"
    content=f"DJANGO_SECRET_KEY={secrets.token_hex(48)}\nPOSTGRES_PASSWORD={secrets.token_hex(32)}\nDJANGO_ALLOWED_HOSTS={domain},localhost,127.0.0.1\nFTBI_DOMAIN={domain}\nFTBI_INSTITUTION_NAME='{args.institution}'\nFTBI_INSTITUTION_SHORT_NAME='{args.short_name}'\n"
    try:
        fd=os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w") as stream: stream.write(content)
    except FileExistsError:
        parser.error(".env already exists; refusing to overwrite secrets")
    print("Created private .env")
    if args.start:
        cmd=["docker","compose"]
        if args.production: cmd+=["-f","compose.production.yaml"]
        def run(*parts): subprocess.run(cmd+list(parts),cwd=root,check=True)
        run("up","-d","db","cache") if args.production else run("up","-d","db")
        run("run","--rm","web","python","manage.py","migrate")
        run("run","--rm","web","python","manage.py","setup_roles")
        run("run","--rm","web","python","manage.py","createsuperuser")
        run("up","-d","--build")
if __name__=="__main__": main()
