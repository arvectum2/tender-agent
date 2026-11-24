#!/opt/homebrew/bin/python3
"""Pinned daily runner. --preflight never runs the workflow or mutates the DB."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path("/Volumes/ArvectumSSD/Arvectum")
HOME = Path("/Users/master")
SHA = "023d3670adcbf6d9ae8a318f4433615fa94b680c"
REVISION = "128_add_tender_async_index_receipts"
RELEASE = BASE / "releases" / ("tender-agent-" + SHA)
MARKER = BASE / "runtime/tender-agent/backend-active.json"
DEPLOY_LOCK = BASE / "runtime/tender-agent/deploy.lock"
LOCK_ROOT = HOME / "Library/Application Support/Arvectum/daily-locks"
RESOURCE_HEALTH = HOME / "ArvectumSafe/runtime/ta-resource-governor/health.json"
DAILY_ENV = HOME / "Library/Application Support/Arvectum/daily-tender-runtime.env"
BACKEND_ENV = HOME / "Library/Application Support/Arvectum/tender-agent/runtime.env"
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PROBE = """
import hashlib,json
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.shared.db.session import engine
with Session(engine) as s:
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('postgres required')
    s.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    row=s.execute(text('''SELECT current_database(),current_user,
          (SELECT oid::text FROM pg_database WHERE datname=current_database()),
          system_identifier::text FROM pg_control_system()''')).one()
    if row[0]!='arvectum' or row[1]!='arvectum' or s.execute(text('select version_num from alembic_version')).scalar_one()!='128_add_tender_async_index_receipts':
        raise RuntimeError('unexpected DB identity')
    if s.execute(text('select pg_is_in_recovery()')).scalar_one():
        raise RuntimeError('standby not permitted')
    s.rollback()
print(hashlib.sha256(json.dumps(list(row),separators=(',', ':')).encode()).hexdigest())
"""


def private_file(path):
    st = path.lstat()
    if path.resolve() != path or not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
        raise ValueError("Unsafe runtime env or marker")


def run_text(args, **kwargs):
    p = subprocess.run(args, capture_output=True, check=False, timeout=18, **kwargs)
    if p.returncode:
        raise RuntimeError("Local preflight command failed")
    return p.stdout


def load_env(path):
    private_file(path)
    minimal = {k: os.environ[k] for k in ("USER", "LOGNAME", "LANG", "TMPDIR") if k in os.environ}
    minimal.update(HOME=str(HOME), PATH=PATH)
    raw = run_text(["/bin/bash", "-c", 'set -a; source "$1"; set +a; /usr/bin/env -0', "daily-env", str(path)],
                   env=minimal, cwd=HOME)
    env = dict(item.decode().split("=",1) for item in raw.split(b"\0") if item)
    for key in list(env):
        if key.startswith("ARVECTUM_WORKSPACE_PROCUREMENT_") or key in ("PYTHONHOME","PYTHONSTARTUP"):
            env.pop(key,None)
    env.update(PATH=PATH, HOME=str(HOME), PYTHONPATH=str(RELEASE/"source"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return env


def no_maintenance():
    if DEPLOY_LOCK.exists() or DEPLOY_LOCK.is_symlink():
        raise RuntimeError("Deployment maintenance active")
    if (LOCK_ROOT/"daily-tender-run.lock").exists():
        raise RuntimeError("Legacy daily lock exists; manual review required")


def check_lock_paths():
    # Legacy parent may be 0755; it must not be writable by other users.
    for path, mask in ((LOCK_ROOT,0o022),(LOCK_ROOT/"v2",0o077)):
        if not path.exists() and not path.is_symlink():
            continue
        st=path.lstat()
        if path.resolve()!=path or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&mask:
            raise RuntimeError("Unsafe daily lock directory")
    path=LOCK_ROOT/"v2/daily-tender-run.flock"
    if path.exists() or path.is_symlink():
        private_file(path)



def require_full_resource_admission(path: Path = RESOURCE_HEALTH, *, now: datetime | None = None) -> None:
    """Reject a new *full* DTR unless current trusted host admission is normal.

    Reduced (batch limit 3) does not admit a full daily run. This never
    interrupts an existing daily process or changes resource governor state.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_uid != os.getuid()
            or meta.st_nlink != 1
            or meta.st_mode & 0o022
            or not 0 < meta.st_size <= 4096
        ):
            raise RuntimeError("Resource admission unavailable")
        raw = os.read(fd, 4097)
        if len(raw) > 4096:
            raise RuntimeError("Resource admission unavailable")
    finally:
        os.close(fd)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("not a JSON object")
        stamp = data.get("checked_at_utc")
        if not isinstance(stamp, str):
            raise TypeError("invalid timestamp")
        observed = datetime.fromisoformat(stamp)
        current = now if now is not None else datetime.now(UTC)
        if observed.tzinfo is None or current.tzinfo is None:
            raise ValueError("timestamp without timezone")
        age = current.astimezone(UTC) - observed.astimezone(UTC)
        if not (
            type(data.get("schema")) is int
            and data["schema"] == 1
            and data.get("status") == "pass"
            and data.get("mode") == "normal"
            and type(data.get("batch_limit")) is int
            and data["batch_limit"] == 10
            and timedelta(0) <= age <= timedelta(seconds=100)
        ):
            raise ValueError("resource admission not normal")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Resource admission unavailable") from exc


def preflight():
    no_maintenance()
    check_lock_paths()
    require_full_resource_admission()
    private_file(MARKER)
    marker=json.loads(MARKER.read_text())
    source=RELEASE/"source"
    python=RELEASE/"venv/bin/python"
    if (marker.get("commit")!=SHA or marker.get("source")!=str(source)
            or marker.get("venv")!=str(RELEASE/"venv") or not python.is_file() or source.resolve()!=source):
        raise RuntimeError("Deployment pin mismatch")
    if run_text(["/usr/bin/git","-C",str(source),"rev-parse","HEAD"]).decode().strip()!=SHA:
        raise RuntimeError("Source pin mismatch")
    if run_text(["/usr/bin/git","-C",str(source),"status","--porcelain","--untracked-files=all"]):
        raise RuntimeError("Release source dirty")
    pid=marker.get("backend_pid")
    if type(pid) is not int or pid<=1:
        raise RuntimeError("Invalid backend marker")
    os.kill(pid,0)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:8001/health",timeout=4) as response:
        if response.status!=200:
            raise RuntimeError("Backend unavailable")
    daily_env=load_env(DAILY_ENV)
    daily_env["ARVECTUM_DAILY_FRESH_PRIORITY_DIRECTORY"]='/Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115/ta-source-discovery-20261114/autonomous-runner'
    backend_env=load_env(BACKEND_ENV)
    a=run_text([str(python),"-c",PROBE],env=daily_env,cwd=HOME).decode().strip()
    b=run_text([str(python),"-c",PROBE],env=backend_env,cwd=HOME).decode().strip()
    if not re.fullmatch("[a-f0-9]{64}",a) or a!=b:
        raise RuntimeError("Daily DB binding differs from backend")
    no_maintenance()
    return daily_env


def acquire_daily_lock():
    check_lock_paths()
    LOCK_ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    private_dir=LOCK_ROOT/"v2"
    private_dir.mkdir(mode=0o700,exist_ok=True)
    check_lock_paths()
    fd=os.open(private_dir/"daily-tender-run.flock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_nlink!=1:
            raise RuntimeError("Unsafe daily lock file")
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight",action="store_true")
    args=parser.parse_args()
    fd=None
    try:
        if not args.preflight:
            fd=acquire_daily_lock()
        env=preflight()
        if args.preflight:
            print("DAILY_PREFLIGHT_OK",SHA,REVISION,"read-only binding match; no workflow executed")
            return 0
        no_maintenance()
        os.chdir(HOME)
        os.set_inheritable(fd,True) # kernel releases flock upon process exit/reboot
        python=str(RELEASE/"venv/bin/python")
        os.execve(python,[python,str(RELEASE/"source/scripts/run_daily_tender_run.py"),"--profile","arvectum-it"],env)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        # Never include command output or env values in launch logs.
        print("DAILY_PREFLIGHT_BLOCKED",type(exc).__name__,file=sys.stderr)
        return 75
    finally:
        if fd is not None:
            os.close(fd)


if __name__=="__main__":
    sys.exit(main())
