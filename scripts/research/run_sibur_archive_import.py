"""Finite resumable SIBUR archive import lane, coordinated with the shared mutation lock."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from scripts.research.capture_sibur_archive import atomic, capture
from src.modules.tender_connectors.sibur.archive_parser import CATEGORIES

MI_PY = "/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python"
API = "arvectum-local-e2e-api-1"
DB = "arvectum-local-e2e-db-1"


def stamp():
    return datetime.now(UTC).isoformat()


def running(root):
    with (root/"archive.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def command(args, cwd=None, timeout=180, data=None):
    p=subprocess.run(args,cwd=cwd,input=data,capture_output=True,timeout=timeout,check=False)
    if p.returncode:
        raise RuntimeError(f"{args[0]} exit {p.returncode}; reconcile before retry")
    return p.stdout


def db_code(repo):
    folder=repo/"scripts/research"
    a=(folder/"import_sibur_public_snapshot.py").read_text().rsplit('if __name__ == "__main__":',1)[0]
    b=(folder/"import_sibur_archive.py").read_text().replace("from __future__ import annotations","").replace(
        "from scripts.research.import_sibur_public_snapshot import SOURCE, build_rows","")
    code=a+"\n"+b
    compile(code,"<archive importer>","exec")
    return code


def backup_ta(root):
    path=root/("sibur-archive-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".dump")
    tmp=path.with_suffix(".partial")
    with tmp.open("xb") as f:
        subprocess.run(["docker","exec",DB,"sh","-c",
                        'exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl'],
                       stdout=f,stderr=subprocess.PIPE,timeout=180,check=True)
        f.flush()
        os.fsync(f.fileno())
    if not tmp.stat().st_size:
        raise ValueError("empty TA backup")
    command(["/opt/homebrew/opt/postgresql@16/bin/pg_restore","-l",str(tmp)],timeout=60)
    tmp.replace(path)
    with path.open("rb") as f:
        return {"file":path.name,"sha256":hashlib.file_digest(f,"sha256").hexdigest()}


def prepare(root, category, pages):
    groups=defaultdict(list)
    evidence=[]
    older=0
    for page in pages:
        path=root/category/f"p{page:05d}.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError("capture receipt not available")
        # Existing receipt ensures capture() takes read-only replay branch.
        receipt, parsed=capture(root,category,page)
        evidence.append(receipt)
        for row in parsed.records:
            day=datetime.strptime(row["published_raw"],"%d.%m.%Y").date()  # noqa: DTZ007
            if day.isoformat()<"2024-01-01":
                older+=1
                continue
            groups[row["external_id"]].append(row)
    accepted,review=[],[]
    for key,obs in groups.items():
        if len({x["published_raw"] for x in obs})!=1:
            review.append({"external_id":key,"observations":obs,"reason":"conflicting publication date"})
        else:
            accepted.append({"external_id":key,"observations":obs})
    return {"schema":"sibur_archive_pages_v1","groups":accepted,"older_rows":older,
            "review":review,"pages":evidence}


def next_batch(root, cursors, active):
    source=json.loads((root/"state.json").read_text()) if (root/"state.json").exists() else {}
    for cat in CATEGORIES:
        start=cursors.get(cat,0)+1
        ready=[]
        for n in range(start,start+25):
            if not (root/cat/f"p{n:05d}.json").exists():
                break
            ready.append(n)
        terminal=source.get(cat,{}).get("status") in {"review","blocked","advertised_pages_traversed","traversed_with_review"}
        if ready and (len(ready)==25 or not active or terminal):
            return cat,ready
    return None


def run(root,runtime,mi,repo,out,state):
    path=out/"state.json"
    def update(**kwargs):
        state.update(kwargs,updated_at=stamp(),pid=os.getpid())
        atomic(path,state)
    if state.get("inflight"):
        update(status="blocked",error="unconfirmed write; verify exact source rows before retry")
        return
    if state.get("status")=="blocked":
        return
    code=db_code(repo)
    while not (out/"STOP").exists():
        active=running(root)
        batch=next_batch(root,state.get("cursors",{}),active)
        if batch is None:
            if not active:
                update(status="finished",step="all captured contiguous pages processed; review source gaps separately")
                return
            update(status="waiting",step="await next 25 verified archive pages")
            time.sleep(15)
            continue
        category,pages=batch
        payload=prepare(root,category,pages)
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()
        sha=hashlib.sha256(raw).hexdigest()
        input_path=out/(sha+".input.json")
        if not input_path.exists():
            with input_path.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if hashlib.sha256(input_path.read_bytes()).hexdigest()!=sha:
            raise ValueError("input provenance mismatch")
        update(status="running",step="wait shared mutation lock",category=category,pages=pages,input_sha256=sha)
        with (runtime/"mutation.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if (out/"STOP").exists():
                update(status="stopped")
                return
            if shutil.disk_usage(out).free < 15*1024**3:
                raise ValueError("disk safety threshold")
            update(step="fresh MI backup and runtime gate")
            command([MI_PY,"-m","scripts.market_intelligence.backup_pq_postgres"],mi)
            gate=json.loads(command([MI_PY,"-m","scripts.market_intelligence.verify_internal_runtime"],mi))
            if gate.get("status")!="pass" or not gate.get("backup",{}).get("sha256"):
                raise ValueError("MI acceptance gate failed")
            backup=backup_ta(out)
            update(step="archive append",inflight=True,backup=backup,mi_backup_sha256=gate["backup"]["sha256"])
            result=json.loads(command(["docker","exec","-i",API,"python","-c",code],repo,600,raw))
            replay=json.loads(command(["docker","exec","-i",API,"python","-c",code],repo,600,raw))
            if replay["inserted"] or replay["before"]!=result["after"]:
                raise ValueError("archive replay not idempotent")
        receipt=out/(sha+".result.json")
        atomic(receipt,{"result":result,"replay":replay,"source_input_sha256":sha,"backup":backup})
        cursors=state.get("cursors",{}).copy()
        cursors[category]=pages[-1]
        update(status="running",step="page batch verified",inflight=False,cursors=cursors,
               inserted_total=state.get("inserted_total",0)+result["inserted"],
               existing_changed_total=state.get("existing_changed_total",0)+result["existing_changed"],
               date_review_total=state.get("date_review_total",0)+len(payload["review"]),
               last_result={k:v for k,v in result.items() if k not in {"pages","changed"}},
               latest_receipt=receipt.name)
    update(status="stopped",step="operator STOP")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("root","runtime","mi","repo"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    os.umask(0o077)
    out=a.root/"import"
    out.mkdir(mode=0o700,exist_ok=True)
    with (out/"import.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("SIBUR archive importer already running")
            return
        path=out/"state.json"
        s=json.loads(path.read_text()) if path.exists() else {"status":"new","cursors":{}}
        try:
            run(a.root,a.runtime,a.mi,a.repo,out,s)
        except Exception as exc:
            s.update(status="blocked",error_type=type(exc).__name__,error=str(exc)[:300],updated_at=stamp())
            atomic(path,s)
            raise


if __name__=="__main__":
    main()
