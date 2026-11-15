"""Independent bounded technical capture and offline evidence scan.

No DB writes; all findings are lexical review candidates. Original archive protocol
worker owns protocol links exclusively, this lane owns other attachments only.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.research.acquire_gpb_documents import capture, references
from scripts.research.capture_gpb_history_partitions import atomic
from scripts.research.technical_document_evidence import extract

SUPPORTED={".zip",".docx",".xlsx",".pptx",".pdf"}
GPB_SUPPORTED={".zip",".docx",".xlsx",".pdf"}


def read(p):
    return json.loads(p.read_text())


def checksum(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def review_extract(original,sha):
    try:
        return extract(original,sha)
    except (ValueError,KeyError,ET.ParseError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
        return {"schema":"technical_document_evidence_v1","source_sha256":sha,"status":"review",
                "parts":[],"review":[{"reason":type(exc).__name__+": "+str(exc)[:150]}]}


def gpb_tasks(details):
    refs=references(details)
    selected=[r for r in refs if r.get("document_role")!="published_protocol"
              and Path(r["original_filename"]).suffix.lower() in GPB_SUPPORTED]
    # Direct office files, then source package names; no repeated URL per procedure.
    unique={(r["external_id"],r["document_url"]):r for r in selected}
    return sorted(unique.values(),key=lambda r:(Path(r["original_filename"]).suffix.lower()==".zip",
                                                r["external_id"],r["document_url"])),len(refs)


def gpb(root,out,limit):
    details=root/"parallel-sources/geh-deadline-archive/detail-lane/details"
    originals=out/"originals"
    originals.mkdir(mode=0o700,exist_ok=True)
    tasks,refs=gpb_tasks(details)
    manifest=out/"capture-receipts.json"
    rows=read(manifest) if manifest.exists() else []
    seen={(r["external_id"],r["document_url"]) for r in rows}
    chosen=[r for r in tasks if (r["external_id"],r["document_url"]) not in seen][:limit]
    state=out/"state.json"
    atomic(state,{"status":"running","selected":len(chosen),"detail_links":refs,"eligible":len(tasks)})
    for r in chosen:
        if (out/"STOP").exists() or shutil.disk_usage(out).free<15*1024**3:
            atomic(state,{"status":"stopped","attempted":len(rows)})
            return
        try:
            rc=capture(out,r)
        except (OSError,ValueError) as exc:
            rc={**r,"capture_status":"review","error":type(exc).__name__,"http_status":getattr(exc,"code",None)}
        rows.append(rc)
        atomic(manifest,rows)
        if rc.get("http_status") in {401,402,403,429,503}:
            atomic(state,{"status":"blocked","attempted":len(rows),"http_status":rc["http_status"]})
            return
        if rc["capture_status"]=="captured":
            path=originals/rc["file"]
            dest=out/(rc["sha256"]+".evidence.json")
            if not dest.exists():
                atomic(dest,review_extract(path,rc["sha256"]))
        time.sleep(1.5)
    # Reconcile exact original bytes and the immutable detail-link evidence.
    task_keys={(r["external_id"],r["document_url"]):r for r in tasks}
    links=[]
    for r in rows:
        if r["capture_status"]!="captured":
            continue
        key=(r["external_id"],r["document_url"])
        if key not in task_keys or any(r[k]!=v for k,v in task_keys[key].items()):
            raise ValueError("technical source reference mismatch")
        p=originals/r["file"]
        if p.is_symlink() or p.parent!=originals or checksum(p)!=r["sha256"]:
            raise ValueError("technical original mismatch")
        links.append({"source_sha256":r["sha256"],"external_id":r["external_id"],
                      "source_url":r["document_url"],"detail_sha256":r["detail_sha256"],"filename":r["original_filename"]})
    report=summary(out,links)
    atomic(out/"report.json",report)
    atomic(state,{"status":"finished","attempted":len(rows),"captured":len(links),"eligible":len(tasks),
                  "report":{k:v for k,v in report.items() if k!="findings"}})
    print(read(state),flush=True)


def sibur(root,out,limit):
    source=root/"sibur-archive-discovery/categories/documents"
    # Verify references against committed TA document captures; only read-only DB access.
    code="""import json,os
from sqlalchemy import create_engine,text
with create_engine(os.environ['AI_CORP_DATABASE_URL']).connect() as c:
 rows=c.execute(text("select t.external_id,d.sha256,d.raw_meta from procurement_tender_documents d join procurement_tenders t on t.id=d.tender_id where t.source='sibur_public'")).mappings()
 print(json.dumps([dict(r) for r in rows],ensure_ascii=False))
"""
    db=json.loads(subprocess.check_output(["docker","exec","arvectum-local-e2e-api-1","python","-c",code],timeout=60))
    known={(r["external_id"],r["sha256"]):r["raw_meta"] for r in db}
    links=[];originals={}
    for f in sorted(source.glob("*.json")):
        if len(f.stem)!=64:
            continue
        r=read(f)
        if r.get("status")!="captured":
            continue
        p=source/r["file"]
        sha=r["sha256"]
        if p.is_symlink() or p.parent!=source or checksum(p)!=sha:
            raise ValueError("SIBUR original mismatch")
        if p.suffix.lower() not in SUPPORTED:
            continue
        for ref in r["references"]:
            meta=known.get((ref["external_id"],sha),{})
            if not any(x["url"]==r["url"] and x["reference"]==ref for x in meta.get("capture_receipts",[])):
                continue
            links.append({"source_sha256":sha,"external_id":ref["external_id"],"source_url":r["url"],
                          "source_row":ref["source_row"],"list_sha256":ref["source_sha256"]})
            originals[sha]=p
    state=out/"state.json"
    count=0
    for sha,p in sorted(originals.items()):
        dest=out/(sha+".evidence.json")
        if dest.exists():
            continue
        if (out/"STOP").exists() or shutil.disk_usage(out).free<15*1024**3 or count>=limit:
            break
        atomic(dest,review_extract(p,sha))
        count+=1
        if count%20==0:
            atomic(state,{"status":"running","processed_new":count,"eligible":len(originals)})
    report=summary(out,links)
    atomic(out/"report.json",report)
    atomic(state,{"status":"finished","processed_new":count,"eligible":len(originals),
                  "report":{k:v for k,v in report.items() if k!="findings"}})
    print(read(state),flush=True)


def summary(out,links):
    by={}
    for r in links:
        by.setdefault(r["source_sha256"],[]).append(r)
    statuses=Counter();categories=Counter();proc={};findings=[]
    for sha,refs in sorted(by.items()):
        p=out/(sha+".evidence.json")
        if not p.exists():
            continue
        e=read(p)
        if e["source_sha256"]!=sha:
            raise ValueError("extraction identity mismatch")
        statuses[e["status"]]+=1
        tags={k for part in e["parts"] for k in part["matches"]}
        categories.update(tags)
        for k in tags:
            proc.setdefault(k,set()).update(r["external_id"] for r in refs)
        if tags:
            findings.append({"source_sha256":sha,"refs":refs,"evidence":e})
    return {"schema":"technical_evidence_report_v1","linked_originals":len(by),"source_links":len(links),
            "processed_originals":sum(statuses.values()),"statuses":dict(statuses),
            "document_categories":dict(categories),"candidate_procedures_by_category":{k:len(v) for k,v in proc.items()},
            "findings":findings}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--mode",choices=["gpb","sibur"],required=True)
    p.add_argument("--limit",type=int,default=100)
    a=p.parse_args();os.umask(0o077)
    if not 1<=a.limit<=300:
        raise ValueError("bounded batch required")
    out=a.root/"technical-evidence"/a.mode
    out.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (out/"executor.lock").open("a") as l:
        fcntl.flock(l,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/"STOP").exists():
            return
        try:
            (gpb if a.mode=="gpb" else sibur)(a.root,out,a.limit)
        except Exception as exc:
            atomic(out/"state.json",{"status":"blocked","error":type(exc).__name__,"reason":str(exc)[:150]})
            raise


if __name__=="__main__":
    main()
