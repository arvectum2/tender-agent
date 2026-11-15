"""Acquire and link source-bound archive documents, independently of the active DP index."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import ssl
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from scripts.research.acquire_sibur_documents import (
    SUPPORTED,
    fetch,
    type_matches,
)
from scripts.research.capture_sibur_archive import atomic
from scripts.research.capture_sibur_public_snapshot import NoRedirect
from scripts.research.import_sibur_public_snapshot import build_rows
from scripts.research.run_sibur_archive_import import (
    API,
    MI_PY,
    backup_ta,
    command,
    prepare,
)
from scripts.research.triage_sibur_document_text import classify_text

ALLOWED=SUPPORTED | {".pptx"}
RESTRICTED={401,402,403,429,503}


def stamp():
    return datetime.now(UTC).isoformat()


def source_refs(root, hashes):
    folder=root/"import"
    state=json.loads((folder/"state.json").read_text())
    cursors=state.get("cursors",{})
    refs=defaultdict(list)
    priority=set()
    ids=set()
    for f in sorted(folder.glob("*.result.json")):
        rc=json.loads(f.read_text())
        sha=rc["source_input_sha256"]
        if f.name!=sha+".result.json" or rc["replay"]["inserted"]:
            raise ValueError("invalid import receipt")
        raw=(folder/(sha+".input.json")).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:
            raise ValueError("archival input integrity mismatch")
        payload=json.loads(raw)
        pages=payload["pages"]
        cat=pages[0]["category"]
        nums=[x["page"] for x in pages]
        if nums[-1]>cursors.get(cat,0):
            continue
        if any(x["category"]!=cat for x in pages) or payload!=prepare(root,cat,nums):
            raise ValueError("raw archive replay mismatch")
        for group in payload["groups"]:
            record=build_rows([group],archive=True)[0]
            key=record["external_id"]
            if hashes.get(key)!=record["content_hash"]:
                continue
            ids.add(key)
            for o in group["observations"]:
                if classify_text(o["title"]+" "+o["subject"]):
                    priority.add(key)
                for url in o["documentation_urls"]:
                    ref={"external_id":key,"source_sha256":o["source_sha256"],
                         "source_row":o["source_row"],"source_url":o["source_url"]}
                    if ref not in refs[url]:
                        refs[url].append(ref)
    return dict(refs),priority,len(ids)


def acquire(out, refs, priority, limit):
    if not 1<=limit<=25:
        raise ValueError("bounded archive batch")
    opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    done=[]
    candidates=sorted(refs,key=lambda u:(not any(r["external_id"] in priority for r in refs[u]),
                 Path(urlsplit(u).path).suffix.lower()==".pdf",u))
    for url in candidates:
        ext=Path(urlsplit(url).path).suffix.lower()
        if ext not in ALLOWED:
            continue
        receipt=out/(hashlib.sha256(url.encode()).hexdigest()+".json")
        if receipt.exists():
            old=json.loads(receipt.read_text())
            if old["url"]!=url:
                raise ValueError("receipt URL mismatch")
            if old["status"]=="captured":
                file=out/old["file"]
                if file.is_symlink() or file.parent!=out or hashlib.sha256(file.read_bytes()).hexdigest()!=old["sha256"]:
                    raise ValueError("captured original mismatch")
                if any(r not in refs[url] for r in old["references"]):
                    raise ValueError("previous source reference missing")
                if old["references"]!=refs[url]:
                    atomic(receipt,{**old,"references":refs[url]})
            continue
        if (out/"STOP").exists() or len(done)>=limit:
            break
        rc={"url":url,"references":refs[url],"observed_at":stamp()}
        try:
            raw,mime=fetch(opener,url)
            if not type_matches(raw,ext):
                raise ValueError("signature mismatch")
            sha=hashlib.sha256(raw).hexdigest()
            file=out/(sha+ext)
            if not file.exists():
                with file.open("xb") as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
            if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest()!=sha:
                raise ValueError("original SHA mismatch")
            rc.update(status="captured",sha256=sha,bytes=len(raw),mime=mime,file=file.name)
        except (ValueError,OSError) as exc:
            rc.update(status="review",error=type(exc).__name__,http_status=getattr(exc,"code",None))
        atomic(receipt,rc)
        done.append(rc)
        if rc.get("http_status") in RESTRICTED:
            raise ValueError("public source access restricted")
        time.sleep(1.5)
    return len(done)


def captures(out,refs):
    rows=[]
    for f in sorted(out.glob("*.json")):
        if len(f.stem)!=64:
            continue
        r=json.loads(f.read_text())
        if r["status"]!="captured":
            continue
        if r["references"]!=refs[r["url"]]:
            raise ValueError("archive reference mismatch")
        path=out/r["file"]
        if (path.is_symlink() or path.parent!=out or path.stem!=r["sha256"]
                or path.stat().st_size!=r["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest()!=r["sha256"]):
            raise ValueError("archive original mismatch")
        rows.append(r)
    return rows


def run(root,runtime,mi,repo,out,state):
    path=out/"state.json"
    def update(**kwargs):
        state.update(kwargs,updated_at=stamp(),pid=os.getpid())
        atomic(path,state)
    if state.get("inflight") or state.get("status")=="blocked":
        update(status="blocked",error="unconfirmed or blocked prior run; reconcile before retry")
        return
    code=(repo/"scripts/research/link_sibur_document_receipts.py").read_text()
    query='''import os,json
from sqlalchemy import create_engine,text
e=create_engine(os.environ["AI_CORP_DATABASE_URL"])
with e.connect() as c:
 print(json.dumps(dict(c.execute(text("select external_id,content_hash from procurement_tenders where source='sibur_public'")).all())))
'''
    while not (out/"STOP").exists():
        if shutil.disk_usage(out).free < 15*1024**3:
            raise ValueError("disk safety threshold")
        update(status="running",step="replay committed archive pages and DB identity")
        hashes=json.loads(command(["docker","exec",API,"python","-c",query],repo,60))
        refs,priority,n=source_refs(root,hashes)
        digest=hashlib.sha256(json.dumps(refs,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        update(step="acquire archive documents",verified_db_rows=n,document_urls=len(refs),
               supported_urls=sum(Path(urlsplit(u).path).suffix.lower() in ALLOWED for u in refs),
               source_refs_sha256=digest)
        attempted=acquire(out,refs,priority,15)
        rows=captures(out,refs)
        payload=json.dumps({"captures":rows,"indexed":{}},ensure_ascii=False).encode()
        sha=hashlib.sha256(payload).hexdigest()
        if rows and state.get("sync_sha")!=sha:
            update(step="wait shared mutation lock",captures=len(rows),pending_sha=sha)
            with (runtime/"mutation.lock").open("a") as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                update(step="fresh MI backup and gate")
                command([MI_PY,"-m","scripts.market_intelligence.backup_pq_postgres"],mi)
                gate=json.loads(command([MI_PY,"-m","scripts.market_intelligence.verify_internal_runtime"],mi))
                if gate.get("status")!="pass" or not gate.get("backup",{}).get("sha256"):
                    raise ValueError("MI acceptance gate failed")
                backup=backup_ta(out)
                update(step="archive document linkage",inflight=True,backup=backup,
                       mi_backup_sha256=gate["backup"]["sha256"])
                args=["docker","exec","-i",API,"python","-c",code]
                result=json.loads(command(args,repo,180,payload))
                repeat=json.loads(command(args,repo,180,payload))
                if repeat["inserted"] or repeat["verified_links"]!=result["verified_links"]:
                    raise ValueError("archive doc replay mismatch")
                atomic(out/f"sync-{sha}.json",{"result":result,"replay":repeat,"backup":backup})
                update(inflight=False,sync_sha=sha,links=result)
        update(captures=len(rows),cycles=state.get("cycles",0)+1)
        if not attempted:
            if json.loads((root/"import/state.json").read_text())["status"] in {"finished","blocked","stopped"}:
                update(status="finished",step="supported archive originals queue drained")
                return
            update(status="waiting",step="await archive imports")
            time.sleep(45)
        else:
            time.sleep(4)
    update(status="stopped")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("root","runtime","mi","repo"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    out=a.root/"documents"
    out.mkdir(mode=0o700,exist_ok=True)
    with (out/"executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("archive document executor already running")
            return
        path=out/"state.json"
        s=json.loads(path.read_text()) if path.exists() else {"status":"new"}
        try:
            run(a.root,a.runtime,a.mi,a.repo,out,s)
        except Exception as exc:
            s.update(status="blocked",error_type=type(exc).__name__,error=str(exc)[:300],updated_at=stamp())
            atomic(path,s)
            raise


if __name__=="__main__":
    main()
