"""Recover incomplete GEH month observations by disjoint verified deadline slices.

Never modify a monthly capture. Split failed pagination/data slices; stop on
transport/access failures. Import only independently completed slices.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import ssl
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from scripts.research.capture_gpb_geh_pages import NoRedirect, page_markers
from scripts.research.capture_gpb_history_partitions import (
    Count,
    archive_rows,
    atomic,
    bounds,
    deadline_calendar_date,
    source_url,
)
from scripts.research.import_gpb_geh_snapshots import normalize
from scripts.research.run_gpb_archive_import import (
    API,
    MI_PY,
    backup_ta,
    command,
    db_code,
)
from src.modules.tender_connectors.etp_gpb.parser import CARD

MONTHS = ("2024-08", "2025-03", "2025-06", "2025-11")
MAX_BYTES = 4_000_000


def slice_url(first, last, page):
    if first > last or first.strftime("%Y-%m") != last.strftime("%Y-%m") or not 1 <= page <= 400:
        raise ValueError("invalid slice range")
    u = urlsplit(source_url(first.strftime("%Y-%m"), page))
    q = dict(parse_qsl(u.query))
    q["procedure[accepted_from]"] = first.strftime("%d.%m.%Y")
    q["procedure[accepted_to]"] = last.strftime("%d.%m.%Y")
    return urlunsplit((u.scheme,u.netloc,u.path,urlencode(q),""))


def split(first, last):
    if first == last:
        return []
    mid = first + timedelta(days=(last-first).days//2)
    return [(first,mid),(mid+timedelta(days=1),last)]


def inspect(raw, first, last, page):
    url=slice_url(first,last,page)
    count=Count()
    count.feed(raw.decode())
    if len(count.values)!=1:
        raise ValueError("missing or ambiguous source result count")
    total=count.values.pop()
    if not total:
        if CARD.search(raw.decode()) or page!=1:
            raise ValueError("zero count contradicts card/page")
        return {"reported_total":0,"expected_pages":1,"ids":[]},[]
    rows=archive_rows(raw,url)
    if any(not first<=deadline_calendar_date(r["deadline_raw"])<=last for r in rows):
        raise ValueError("deadline outside slice")
    pages=(total+19)//20
    current,exposed=page_markers(raw) if total>20 else (1,1)
    if current!=page or exposed!=pages or page>pages or len(rows)!=min(20,total-20*(page-1)):
        raise ValueError("slice pagination mismatch")
    return {"reported_total":total,"expected_pages":pages,"ids":[r["external_id"] for r in rows]},rows


def capture(folder, first,last,page):
    receipt=folder/f"p{page:04d}.json"
    url=slice_url(first,last,page)
    if receipt.exists():
        rc=json.loads(receipt.read_text())
        p=folder/rc["file"]
        if p.is_symlink() or p.parent!=folder or rc["url"]!=url:
            raise ValueError("invalid saved receipt")
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=rc["sha256"]:
            raise ValueError("saved original SHA mismatch")
    else:
        op=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
        with op.open(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as res:
            raw=res.read(MAX_BYTES+1)
            if res.status!=200 or res.geturl()!=url or len(raw)>MAX_BYTES:
                raise OSError("unexpected source response")
        sha=hashlib.sha256(raw).hexdigest()
        p=folder/f"p{page:04d}-{sha}.html"
        if not p.exists():
            with p.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if p.is_symlink() or p.read_bytes()!=raw:
            raise ValueError("saved source collision")
        rc={"url":url,"sha256":sha,"file":p.name,"observed_at":datetime.now(UTC).isoformat(),"page":page}
        atomic(receipt,rc)
        time.sleep(1.5)
    scope,rows=inspect(raw,first,last,page)
    if "scope" in rc and rc["scope"]!=scope:
        raise ValueError("prior scope mismatch")
    if "scope" not in rc:
        rc["scope"]=scope
        atomic(receipt,rc)
    return rc,rows


def complete_slice(root,first,last):
    key=f"{first}_{last}"
    folder=root/"slices"/key
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    rc,rows=capture(folder,first,last,1)
    total=rc["scope"]["reported_total"]
    count=rc["scope"]["expected_pages"]
    receipts=[rc]
    entries=[{"observation":row,"observed_at":rc["observed_at"]} for row in rows]
    for page in range(2,count+1):
        if (root/"STOP").exists() or shutil.disk_usage(root).free<15*1024**3:
            raise OSError("operator stop or disk threshold")
        rc,rows=capture(folder,first,last,page)
        if rc["scope"]["reported_total"]!=total:
            raise ValueError("source count drift")
        receipts.append(rc)
        entries.extend({"observation":row,"observed_at":rc["observed_at"]} for row in rows)
    ids=[e["observation"]["external_id"] for e in entries]
    if len(ids)!=total or len(set(ids))!=total:
        raise ValueError("slice repeated or missing identity")
    return {"month":key,"calendar_month":first.strftime("%Y-%m"),"first":str(first),"last":str(last),
            "count":total,"page_sha256":[x["sha256"] for x in receipts]},entries


def collect(root,first,last,state,leaves,entries):
    if (root/"STOP").exists():
        raise OSError("operator STOP")
    key=f"{first}_{last}"
    try:
        manifest,rows=complete_slice(root,first,last)
    except ValueError as exc:
        parts=split(first,last)
        state["slices"][key]={"status":"split" if parts else "review","reason":str(exc)[:200]}
        atomic(root/"state.json",state)
        for a,b in parts:
            collect(root,a,b,state,leaves,entries)
    else:
        leaves.append(manifest)
        entries.extend(rows)
        state["slices"][key]={"status":"verified_complete","count":manifest["count"],
                              "pages":len(manifest["page_sha256"])}
        atomic(root/"state.json",state)


def prepare(root,month,state):
    first,last=bounds(month)
    leaves,entries=[],[]
    for a,b in split(first,last):
        collect(root,a,b,state,leaves,entries)
    accepted,review=[],[]
    seen=set()
    for entry in entries:
        try:
            norm=normalize(entry)
            if norm["external_id"] in seen:
                raise ValueError("cross-slice repeated identity")
        except (ValueError,KeyError) as exc:
            review.append({"entry":entry,"reason":str(exc)})
        else:
            seen.add(norm["external_id"])
            accepted.append(entry)
    return {"schema":"gpb_deadline_archive_v1","accepted":accepted,
            "review":review,"completed_partitions":leaves}


def run(root,archive,runtime,mi,repo,months):
    state_path=root/"state.json"
    state=json.loads(state_path.read_text()) if state_path.exists() else {"status":"new","months":{},"slices":{}}
    out=root/"import"
    out.mkdir(mode=0o700,exist_ok=True)
    ip=out/"state.json"
    imp=json.loads(ip.read_text()) if ip.exists() else {"status":"new","imported_months":[],"inserted_total":0}
    if imp.get("inflight") or imp.get("status")=="blocked":
        raise RuntimeError("prior import unconfirmed or blocked; reconcile first")
    original=json.loads((archive/"state.json").read_text())
    try:
        for month in months:
            if state["months"].get(month,{}).get("status") in {"verified_complete","partial_imported"}:
                continue
            state.update(status="running",month=month)
            atomic(state_path,state)
            payload=prepare(root,month,state)
            manifests=payload["completed_partitions"]
            total=sum(v["count"] for v in manifests)
            expected=original[month]["source_count"]
            unique=len({e["observation"]["external_id"] for e in payload["accepted"]+[
                x["entry"] for x in payload["review"]]})
            coverage_days=sum((date.fromisoformat(m["last"])-date.fromisoformat(m["first"])).days+1 for m in manifests)
            complete=coverage_days==bounds(month)[1].day and expected==total==unique
            info={"status":"prepared","source_reported_month_count":expected,
                  "verified_slice_rows":total,"unique_ids":unique,"verified_days":coverage_days,
                  "month_complete":complete,"accepted":len(payload["accepted"]),"review":len(payload["review"])}
            state["months"][month]=info
            atomic(state_path,state)
            if not payload["accepted"]:
                info["status"]="review"
                atomic(state_path,state)
                continue
            raw=json.dumps(payload,ensure_ascii=False).encode()
            sha=hashlib.sha256(raw).hexdigest()
            p=out/(sha+".input.json")
            if not p.exists():
                with p.open("xb") as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
            if p.read_bytes()!=raw:
                raise ValueError("import input mismatch")
            imp.update(status="running",step="wait shared lock",month=month,input_sha256=sha)
            atomic(ip,imp)
            with (runtime/"mutation.lock").open("a") as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                if (root/"STOP").exists():
                    raise OSError("operator STOP before write")
                if shutil.disk_usage(root).free<15*1024**3:
                    raise OSError("disk safety threshold")
                command([MI_PY,"-m","scripts.market_intelligence.backup_pq_postgres"],mi,180)
                gate=json.loads(command([MI_PY,"-m","scripts.market_intelligence.verify_internal_runtime"],mi,180))
                if gate.get("status")!="pass" or not gate.get("backup",{}).get("sha256"):
                    raise ValueError("MI acceptance gate failed")
                backup=backup_ta(out)
                imp.update(inflight=True,step="append verified slices",backup=backup,mi_backup_sha256=gate["backup"]["sha256"])
                atomic(ip,imp)
                args=["docker","exec","-i",API,"python","-c",db_code(repo)]
                result=json.loads(command(args,repo,600,raw))
                replay=json.loads(command(args,repo,600,raw))
                if replay["inserted"] or replay["before"]!=result["after"]:
                    raise ValueError("replay mismatch")
                atomic(out/(sha+".result.json"),{"result":result,"replay":replay,"backup":backup,"source_input_sha256":sha})
                imp.update(inflight=False,step="verified commit",imported_months=sorted(set(imp["imported_months"]+[v["month"] for v in manifests])),
                           inserted_total=imp["inserted_total"]+result["inserted"],latest_receipt=sha+".result.json")
                atomic(ip,imp)
            info.update(status="verified_complete" if complete else "partial_imported",
                        inserted=result["inserted"],replay_inserted=replay["inserted"],input_sha256=sha)
            atomic(state_path,state)
            print(month,info,flush=True)
        state["status"]="finished"
        imp["status"]="finished"
    except Exception as exc:
        state.update(status="blocked",error_type=type(exc).__name__,error=str(exc)[:300])
        imp.update(status="blocked",error_type=type(exc).__name__)
        raise
    finally:
        atomic(state_path,state)
        atomic(ip,imp)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("archive","runtime","mi","repo","root"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--months",nargs="+",choices=MONTHS,required=True)
    a=p.parse_args();os.umask(0o077)
    if len(a.months)!=len(set(a.months)):
        raise ValueError("duplicate months")
    a.root.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (a.root/"executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("slice repair already running")
            return
        run(a.root,a.archive,a.runtime,a.mi,a.repo,a.months)


if __name__=="__main__":
    main()
