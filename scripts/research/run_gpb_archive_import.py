"""One finite local archive-import lane; wait for verified partitions and never overwrite prior rows."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.research.capture_gpb_history_partitions import atomic
from scripts.research.prepare_gpb_history_import import prepare

MI_PY = "/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python"
API = "arvectum-local-e2e-api-1"
DB = "arvectum-local-e2e-db-1"


def stamp():
    return datetime.now(UTC).isoformat()


def db_code(repo):
    research = repo / "scripts/research"
    base = (research / "import_gpb_geh_snapshots.py").read_text()
    extra = (research / "import_gpb_archive_observations.py").read_text()
    base = base.rsplit('if __name__ == "__main__":', 1)[0]
    extra = extra.replace('from __future__ import annotations', '').replace(
        'from scripts.research.import_gpb_geh_snapshots import import_rows, normalize', '')
    code = base + "\n" + extra
    compile(code, "<verified archive importer>", "exec")
    return code


def source_running(archive):
    with (archive / "archive.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def command(args, cwd=None, timeout=180, data=None):
    proc = subprocess.run(args, cwd=cwd, input=data, capture_output=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError(f"{args[0]} failed (exit {proc.returncode}); reconcile before any retry")
    return proc.stdout


def backup_ta(folder):
    dest = folder / ("archive-ta-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".dump")
    partial = dest.with_suffix(".partial")
    with partial.open("xb") as f:
        subprocess.run(["docker", "exec", DB, "sh", "-c",
                        'exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl'],
                       stdout=f, stderr=subprocess.PIPE, timeout=180, check=True)
        f.flush()
        os.fsync(f.fileno())
    if not partial.stat().st_size:
        raise ValueError("empty DB backup")
    command(["/opt/homebrew/opt/postgresql@16/bin/pg_restore", "-l", str(partial)], timeout=60)
    partial.replace(dest)
    with dest.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return {"file": dest.name, "sha256": sha}


def execute(archive, runtime, mi, repo, out, state):
    state_file = out / "state.json"
    def update(**kw):
        state.update(kw, updated_at=stamp(), pid=os.getpid())
        atomic(state_file, state)
    if state.get("inflight"):
        update(status="blocked", error="Previous import unconfirmed; compare exact source IDs and hashes before retry")
        return
    if state.get("status") == "blocked":
        return
    code = db_code(repo)
    while not (out/"STOP").exists():
        source = json.loads((archive/"state.json").read_text())
        imported = state.get("imported_months", [])
        ready = sorted(m for m, r in source.items() if r["status"] == "verified_complete" and m not in imported)
        if not ready:
            if not source_running(archive):
                update(status="finished", step="all currently verified months imported", source_statuses=source)
                return
            update(status="waiting", step="await next completed archive partition")
            time.sleep(12)
            continue
        # A bounded transaction for accumulated completed months; old observations never replaced.
        batch = ready[:3]
        payload = prepare(archive, batch)
        data = json.dumps(payload, ensure_ascii=False).encode()
        digest = hashlib.sha256(data).hexdigest()
        path = out / (digest+".input.json")
        if not path.exists():
            with path.open("xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("archive input mismatch")
        update(status="running", step="waiting shared mutation lock", batch=batch, input_sha256=digest)
        with (runtime/"mutation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (out/"STOP").exists():
                update(status="stopped")
                return
            if shutil.disk_usage(out).free < 15*1024**3:
                raise ValueError("disk safety threshold reached")
            update(step="fresh MI backup and gate")
            command([MI_PY, "-m", "scripts.market_intelligence.backup_pq_postgres"], mi, 180)
            gate = json.loads(command([MI_PY, "-m", "scripts.market_intelligence.verify_internal_runtime"], mi, 180))
            if gate.get("status") != "pass" or not gate.get("backup", {}).get("sha256"):
                raise ValueError("MI acceptance gate failed")
            backup = backup_ta(out)
            update(step="DB append", inflight=True, backup=backup, mi_backup_sha256=gate["backup"]["sha256"])
            result = json.loads(command(["docker", "exec", "-i", API, "python", "-c", code], repo, 600, data))
            replay = json.loads(command(["docker", "exec", "-i", API, "python", "-c", code], repo, 600, data))
            if replay["inserted"] or replay["before"] != result["after"]:
                raise ValueError("archive replay failed")
        receipt = out / (digest+".result.json")
        atomic(receipt, {"result": result, "replay": replay, "backup": backup, "source_input_sha256": digest})
        update(status="running", step="month commit verified", inflight=False,
               imported_months=sorted(set(imported+batch)),
               inserted_total=state.get("inserted_total", 0)+result["inserted"],
               last_result={k:v for k,v in result.items() if k not in {"changed", "completed_partitions"}},
               latest_receipt=receipt.name)
    update(status="stopped", step="operator STOP")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("archive","runtime","mi","repo"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    os.umask(0o077)
    out=a.archive/"import"
    out.mkdir(mode=0o700,exist_ok=True)
    with (out/"import.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("archive importer already running")
            return
        state_file=out/"state.json"
        state=json.loads(state_file.read_text()) if state_file.exists() else {"status":"new","imported_months":[]}
        try:
            execute(a.archive,a.runtime,a.mi,a.repo,out,state)
        except Exception as exc:
            state.update(status="blocked", error_type=type(exc).__name__, error=str(exc)[:300],updated_at=stamp())
            atomic(state_file,state)
            raise


if __name__ == "__main__":
    main()
