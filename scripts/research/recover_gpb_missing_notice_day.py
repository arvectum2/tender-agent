"""Recover valid rows on June 4 while retaining missing source notice in review."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import ssl
import time
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from scripts.research.capture_gpb_geh_pages import NoRedirect, page_markers
from scripts.research.capture_gpb_history_partitions import (
    Count,
    archive_rows,
    atomic,
    deadline_calendar_date,
)
from scripts.research.import_gpb_geh_snapshots import normalize
from scripts.research.repair_gpb_date_slices import slice_url
from scripts.research.run_gpb_archive_import import (
    API,
    MI_PY,
    backup_ta,
    command,
    db_code,
)
from src.modules.tender_connectors.etp_gpb.parser import CARD, NATIVE, ORIGIN, Card

DAY=date(2025,6,4)
EXPECTED=56


def parse_page(raw,url,page):
    q=Count()
    q.feed(raw.decode())
    if q.values!={EXPECTED} or page_markers(raw)!=(page,3):
        raise ValueError("unexpected day count or page")
    cards=CARD.findall(raw.decode())
    if len(cards)!=min(20,EXPECTED-20*(page-1)):
        raise ValueError("unexpected row count")
    digest=hashlib.sha256(raw).hexdigest()
    rows,review=[],[]
    for ordinal,html in enumerate(cards,1):
        try:
            row=archive_rows(html.encode(),url)[0]
        except ValueError as exc:
            c=Card()
            c.feed(html)
            links=[]
            for href,label in c.links:
                u=urlsplit(urljoin(ORIGIN,href))
                m=NATIVE.fullmatch(u.path)
                if u.scheme=="https" and u.netloc=="etpgpb.ru" and m:
                    links.append((u.geturl(),m.groups(),label))
            if (str(exc)!="missing source identity or title" or len(links)<2
                    or len({v[1] for v in links})!=1 or links[0][2]!="-" or not links[1][2]):
                raise ValueError("unexpected malformed card") from exc
            section,native=links[0][1]
            review.append({"external_id":section+":"+native,"source_sha256":digest,"source_row":ordinal,
                           "source_url":url,"number_raw":"-","title":links[1][2],
                           "detail_url":links[0][0],"reason":"SOURCE_NOTICE_NUMBER_ABSENT"})
            continue
        if deadline_calendar_date(row["deadline_raw"])!=DAY:
            raise ValueError("outside exact calendar day")
        row.update(source_sha256=digest,source_row=ordinal)
        rows.append(row)
    return rows,review


def prepare(prior,out):
    accepted,review,ids,hashes=[],[],set(),[]
    folder=prior/"slices/2025-06-04_2025-06-04"
    for page in range(1,4):
        url=slice_url(DAY,DAY,page)
        receipt=out/f"p{page:04d}.json"
        if receipt.exists():
            rc=json.loads(receipt.read_text())
            raw=(out/rc["file"]).read_bytes()
        elif page==1:
            rc=json.loads((folder/"p0001.json").read_text())
            raw=(folder/rc["file"]).read_bytes()
        else:
            with build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context())).open(
                Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as resp:
                raw=resp.read(4_000_001)
                if resp.status!=200 or resp.geturl()!=url or len(raw)>4_000_000:
                    raise ValueError("unexpected HTTP result")
            sha=hashlib.sha256(raw).hexdigest()
            rc={"url":url,"sha256":sha,"file":f"p{page:04d}-{sha}.html","observed_at":datetime.now(UTC).isoformat(),"page":page}
            time.sleep(1.5)
        if rc["url"]!=url or rc["sha256"]!=hashlib.sha256(raw).hexdigest():
            raise ValueError("page identity mismatch")
        path=out/rc["file"]
        if not path.exists():
            with path.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if path.is_symlink() or path.read_bytes()!=raw:
            raise ValueError("original mismatch")
        if not receipt.exists():
            atomic(receipt,rc)
        rows,invalid=parse_page(raw,url,page)
        hashes.append(rc["sha256"])
        for row in rows:
            entry={"observation":row,"observed_at":rc["observed_at"]}
            normalize(entry)
            accepted.append(entry)
        review.extend(invalid)
        page_ids=[r["external_id"] for r in rows+invalid]
        if len(set(page_ids))!=len(page_ids) or ids.intersection(page_ids):
            raise ValueError("day identities repeated")
        ids.update(page_ids)
    if len(ids)!=EXPECTED or len(review)!=1 or review[0]["external_id"]!="etp:1123151":
        raise ValueError("unexpected day identity audit")
    return {"schema":"gpb_deadline_archive_v1","accepted":accepted,"review":review,
            "completed_partitions":[{"month":"2025-06-04_2025-06-04","calendar_month":"2025-06","count":len(ids),
            "page_sha256":hashes,"verification":"ALL_SOURCE_IDENTITIES_ACCOUNTED_FOR_NOTICE_MISSING_REVIEW"}]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("prior","root","runtime","repo","mi"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    a.root.mkdir(mode=0o700,parents=True,exist_ok=True)
    out=a.root/"import";out.mkdir(mode=0o700,exist_ok=True)
    state=out/"state.json"
    with (out/"executor.lock").open("a") as l:
        fcntl.flock(l,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if state.exists():
            old=json.loads(state.read_text())
            if old.get("status")=="finished":
                return
            if old.get("inflight") or old.get("status")=="blocked":
                raise ValueError("prior attempt requires reconciliation")
        payload=prepare(a.prior,a.root)
        raw=json.dumps(payload,ensure_ascii=False).encode();sha=hashlib.sha256(raw).hexdigest()
        path=out/(sha+".input.json")
        if not path.exists():
            with path.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if path.read_bytes()!=raw:
            raise ValueError("input mismatch")
        s={"status":"running","step":"wait shared lock","input_sha256":sha,"inserted_total":0,
           "imported_months":[],"accepted":len(payload["accepted"]),"review":len(payload["review"])}
        atomic(state,s)
        try:
            with (a.runtime/"mutation.lock").open("a") as guard:
                fcntl.flock(guard,fcntl.LOCK_EX)
                if (a.root/"STOP").exists():
                    raise ValueError("operator STOP")
                command([MI_PY,"-m","scripts.market_intelligence.backup_pq_postgres"],a.mi,180)
                gate=json.loads(command([MI_PY,"-m","scripts.market_intelligence.verify_internal_runtime"],a.mi,180))
                if gate.get("status")!="pass" or not gate.get("backup",{}).get("sha256"):
                    raise ValueError("MI gate failed")
                backup=backup_ta(out)
                s.update(inflight=True,step="append verified day",backup=backup,mi_backup_sha256=gate["backup"]["sha256"])
                atomic(state,s)
                args=["docker","exec","-i",API,"python","-c",db_code(a.repo)]
                result=json.loads(command(args,a.repo,600,raw))
                replay=json.loads(command(args,a.repo,600,raw))
                if replay["inserted"] or replay["before"]!=result["after"]:
                    raise ValueError("day replay mismatch")
                atomic(out/(sha+".result.json"),{"result":result,"replay":replay,"backup":backup,"source_input_sha256":sha})
                s.update(status="finished",inflight=False,step="verified day commit",inserted_total=result["inserted"],
                         imported_months=["2025-06-04_2025-06-04"],latest_receipt=sha+".result.json")
                atomic(state,s)
        except Exception as exc:
            s.update(status="blocked",error=str(exc)[:200])
            atomic(state,s)
            raise
        print(s,flush=True)


if __name__=="__main__":
    main()
