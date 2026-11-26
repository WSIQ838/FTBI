"""Managed encrypted-backup inventory. Retention is a dry run unless explicitly applied."""
import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path

ARCHIVE=re.compile(r"ftbi-([0-9]{8}T[0-9]{6}Z)(?:-[A-Za-z0-9]+)?\.dump\.age")


def now(): return datetime.now(timezone.utc)
def stamp(): return now().isoformat()


def atomic_json(path,data):
    descriptor,name=tempfile.mkstemp(prefix=".catalog-",dir=path.parent)
    try:
        with os.fdopen(descriptor,"w",encoding="utf-8") as stream:
            json.dump(data,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def initialize(directory):
    root=Path(directory).absolute()
    if root.is_symlink(): raise ValueError("Backup root must not be a symbolic link")
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    root=root.resolve()
    if list(root.iterdir()): raise ValueError("Initialize an empty backup directory only")
    atomic_json(root/".ftbi-backup-store.json",{"version":1,"identity":secrets.token_hex(16),"directory":str(root)})
    return root


def store(directory):
    original=Path(directory).absolute()
    if original.is_symlink(): raise ValueError("Backup root must not be a symbolic link")
    root=original.resolve(strict=True)
    marker=root/".ftbi-backup-store.json"
    if marker.is_symlink() or not marker.is_file(): raise ValueError("Backup directory is not initialized")
    data=json.loads(marker.read_text(encoding="utf-8"))
    if data.get("version")!=1 or data.get("directory")!=str(root): raise ValueError("Backup store identity does not match this directory")
    return root


@contextmanager
def locked(root):
    path=root/".catalog.lock"
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        os.close(descriptor)
        yield
    finally: path.unlink()


def archive_path(root,name):
    if not isinstance(name,str) or not ARCHIVE.fullmatch(name): raise ValueError("Unexpected archive name")
    path=root/name
    if path.is_symlink() or path.resolve().parent!=root: raise ValueError("Archive escapes managed directory")
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size<=0: raise ValueError("Archive must be a nonempty private regular file")
    return path


def sha256(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()


def _record(root,name):
    archive=archive_path(root,name)
    manifest=root/(name+".json")
    if manifest.exists() or manifest.is_symlink(): raise ValueError("Archive already has a manifest")
    data={"version":1,"archive":name,"created":stamp(),"bytes":archive.stat().st_size,"sha256":sha256(archive),"verified_restore_at":None}
    atomic_json(manifest,data)
    return data


def record(directory,name):
    root=store(directory)
    with locked(root): return _record(root,name)


def inventory(root):
    entries=[]
    for manifest in root.glob("ftbi-*.dump.age.json"):
        if manifest.is_symlink(): raise ValueError("Manifest must not be a symbolic link")
        data=json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("version")!=1 or manifest.name!=data.get("archive","")+".json": raise ValueError("Manifest identity mismatch")
        archive=archive_path(root,data["archive"])
        if archive.stat().st_size!=data["bytes"] or sha256(archive)!=data["sha256"]: raise ValueError("Backup integrity mismatch; retention stopped")
        created=datetime.fromisoformat(data["created"])
        if created.tzinfo is None or created>now()+timedelta(minutes=5): raise ValueError("Invalid backup timestamp")
        if data.get("verified_restore_at"):
            verified=datetime.fromisoformat(data["verified_restore_at"])
            if verified.tzinfo is None or verified<created or verified>now()+timedelta(minutes=5): raise ValueError("Invalid restore verification timestamp")
        entries.append(data)
    return sorted(entries,key=lambda entry:(entry["created"],entry["archive"]),reverse=True)


def mark_restored(directory,name):
    root=store(directory)
    with locked(root):
        entry=next((entry for entry in inventory(root) if entry["archive"]==name),None)
        if entry is None: raise ValueError("No managed archive found")
        entry["verified_restore_at"]=stamp();atomic_json(root/(name+".json"),entry)
    return entry


def prune(directory,days=30,keep=7,apply=False):
    if not 7<=days<=36500 or not 2<=keep<=1000: raise ValueError("Keep at least seven days and two archives")
    root=store(directory)
    with locked(root):
        entries=inventory(root)
        cutoff=now()-timedelta(days=days)
        verified=[entry for entry in entries[:keep] if entry.get("verified_restore_at")]
        candidates=[]
        if verified:
            newest_verified=max(entry["created"] for entry in verified)
            for entry in entries[keep:]:
                if datetime.fromisoformat(entry["created"])<cutoff and entry["created"]<newest_verified: candidates.append(entry["archive"])
        if apply:
            for name in candidates:
                archive_path(root,name).unlink()
                (root/(name+".json")).unlink()
        return {"applied":apply,"candidates":candidates,"kept":len(entries)-len(candidates),"restore_gate_satisfied":bool(verified)}


def run_backup(directory):
    root=store(directory)
    with locked(root):
        status_path=root/".backup-status.json"
        previous=json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() and not status_path.is_symlink() else {}
        status={"last_attempt":stamp(),"last_success":previous.get("last_success"),"result":"running"}
        atomic_json(status_path,status)
        env=os.environ.copy();env["BACKUP_DIR"]=str(root)
        try:
            script=Path(__file__).with_name("backup-encrypted.sh")
            # Execute only the fixed local script; arguments are never interpolated by a shell.
            result=subprocess.run(["sh",str(script)],env=env,check=True,capture_output=True,text=True,timeout=3600)
            output=Path(result.stdout.strip())
            if output.parent.resolve()!=root: raise ValueError("Backup output outside managed directory")
            entry=_record(root,output.name)
        except Exception:
            status["result"]="failed";atomic_json(status_path,status)
            raise RuntimeError("Encrypted backup failed; inspect the trusted local backup environment") from None
        status.update(result="success",last_success=stamp(),archive=entry["archive"])
        atomic_json(status_path,status)
        return entry


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["init","run","record","mark-restored","prune"])
    parser.add_argument("directory")
    parser.add_argument("--archive")
    parser.add_argument("--days",type=int,default=30)
    parser.add_argument("--keep",type=int,default=7)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if args.action=="init": result={"directory":str(initialize(args.directory))}
    elif args.action=="run": result=run_backup(args.directory)
    elif args.action=="record": result=record(args.directory,args.archive)
    elif args.action=="mark-restored": result=mark_restored(args.directory,args.archive)
    else: result=prune(args.directory,args.days,args.keep,args.apply)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__": main()
