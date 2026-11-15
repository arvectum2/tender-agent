"""Independent archival detail/protocol lane with immutable evidence."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from scripts.research import acquire_gpb_documents as docs
from scripts.research.autonomous_runner import Blocked, Runner, atomic, read, utc
from scripts.research.capture_gpb_priority_details import capture
from scripts.research.triage_gpb_archive_imports import build

LANE = "archive-details"
RESTRICTED = {401,402,403,429,503}


def select(queue, reserved, seen, limit):
    return [r for r in queue["candidates"] if r["external_id"] not in reserved|seen][:limit]


class ArchiveRunner(Runner):
    def __init__(self, root, repo, mi):
        self.shared = root/"autonomous-runner"
        self.archive = root/"parallel-sources/geh-deadline-archive"
        self.original = root/"parallel-sources"
        isolated = self.archive/"detail-lane"
        isolated.mkdir(mode=0o700,exist_ok=True)
        super().__init__(isolated,repo,repo,mi)
        self.output=isolated/"details"
        self.output.mkdir(mode=0o700,exist_ok=True)
        (self.output/"originals").mkdir(mode=0o700,exist_ok=True)

    @contextmanager
    def mutation_guard(self):
        with (self.shared/"mutation.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            yield

    def refresh(self):
        code='''import os,json
from sqlalchemy import create_engine,text
e=create_engine(os.environ["AI_CORP_DATABASE_URL"])
with e.connect() as c:
 print(json.dumps(dict(c.execute(text("select external_id,content_hash from procurement_tenders where source='etp_gpb'")).all())))
'''
        hashes=json.loads(self.cmd(LANE,"read-only DB hashes",["docker","exec","arvectum-local-e2e-api-1","python","-c",code],self.gpb,60))
        folders=[self.archive/"import"]
        for p in sorted(self.archive.glob("repair-*-complete-*")):
            if (p/"import/state.json").exists():
                folders.append(p/"import")
        queue=build(folders,hashes)
        reserved={r["external_id"] for r in read(self.original/"geh-metadata-priority-history400.json")}
        queue["candidates"]=select(queue,reserved,set(),len(queue["candidates"]))
        raw=json.dumps(queue,ensure_ascii=False,sort_keys=True).encode()
        sha=hashlib.sha256(raw).hexdigest()
        path=self.run/f"queue-{sha}.json"
        if not path.exists():
            with path.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        elif path.read_bytes()!=raw:
            raise Blocked("queue hash mismatch")
        self.update(LANE,queue_sha256=sha,queue_candidates=len(queue["candidates"]),
                    verified_db_rows=queue["verified_db_rows"])
        return queue

    def capture_details(self,queue):
        p=self.output/"receipts.json"
        review=self.output/"review.json"
        rows=read(p) if p.exists() else []
        reviews=read(review) if review.exists() else {}
        seen={r["external_id"] for r in rows}|set(reviews)
        selected=select(queue,set(),seen,15)
        self.update(LANE,step="capture archive detail batch",selected=len(selected))
        for row in selected:
            if self.stop_requested():
                break
            ident=row["external_id"]
            try:
                rc=capture(self.output,row["entry"]["observation"])
                rows.append(rc)
                atomic(p,rows)
            except (OSError,ValueError) as exc:
                reviews[ident]={"error":type(exc).__name__,"reason":str(exc)[:180],
                                "http_status":getattr(exc,"code",None),"observed_at":utc()}
                atomic(review,reviews)
                if getattr(exc,"code",None) in RESTRICTED:
                    raise Blocked("source detail access restricted")
            time.sleep(1)
        if not p.exists():
            atomic(p,rows)
        return len(selected)

    def capture_protocols(self):
        p=self.output/"document-pilot-receipts.json"
        rows=read(p) if p.exists() else []
        seen={(r["external_id"],r["document_url"]) for r in rows}
        tasks=[r for r in docs.references(self.output) if r.get("document_role")=="published_protocol"
               and Path(r["original_filename"]).suffix.lower() in docs.SUPPORTED
               and (r["external_id"],r["document_url"]) not in seen][:30]
        self.update(LANE,step="capture archive protocols",selected_documents=len(tasks))
        for row in tasks:
            if self.stop_requested():
                break
            try:
                rc=docs.capture(self.output,row)
            except (OSError,ValueError) as exc:
                rc={**row,"capture_status":"review","error":type(exc).__name__,"http_status":getattr(exc,"code",None)}
            rows.append(rc)
            atomic(p,rows)
            if rc.get("http_status") in RESTRICTED:
                raise Blocked("source protocol access restricted")
            time.sleep(1)
        if not p.exists():
            atomic(p,rows)
        return len(tasks)

    def sync(self):
        # Verify the entire source set once, then parse decisions from those exact receipts.
        prepared=json.loads(self.module(LANE,self.gpb,"prepare_gpb_archive_sync",self.output,timeout=600))
        links=prepared["links_json"].encode()
        decisions=prepared["decisions_json"].encode()
        sha=hashlib.sha256(links+decisions).hexdigest()
        if self.state["lanes"][LANE].get("sync_sha")==sha or not json.loads(links):
            return
        with self.mutation_guard():
            self.gate(LANE)
            self.backup_ta(LANE)
            self.update(LANE,inflight=True,pending_sha=sha)
            linked=self.importer(LANE,self.gpb,"link_gpb_document_receipts",links)
            outcomes=self.importer(LANE,self.gpb,"persist_gpb_protocol_decisions",decisions)
            repeat_links=self.importer(LANE,self.gpb,"link_gpb_document_receipts",links)
            repeat=self.importer(LANE,self.gpb,"persist_gpb_protocol_decisions",decisions)
            if repeat["updated"] or repeat_links["inserted"]:
                raise Blocked("archive detail replay not idempotent")
            atomic(self.run/f"sync-{sha}.json",{"links":linked,"outcomes":outcomes,
                                               "replay_links":repeat_links,"replay_outcomes":repeat})
            self.update(LANE,inflight=False,sync_sha=sha,links=linked,outcomes=outcomes)

    def lane(self):
        state=self.state["lanes"].get(LANE,{})
        if state.get("inflight") or state.get("status")=="blocked":
            raise Blocked("previous unconfirmed or blocked lane; reconcile first")
        while not self.stop_requested():
            if shutil.disk_usage(self.root).free<15*1024**3:
                raise Blocked("disk threshold")
            queue=self.refresh()
            a=self.capture_details(queue)
            b=self.capture_protocols()
            self.sync()
            self.update(LANE,details=len(read(self.output/"receipts.json")),
                        document_receipts=len(read(self.output/"document-pilot-receipts.json")),
                        cycles=self.state["lanes"][LANE].get("cycles",0)+1)
            if not a and not b:
                status=read(self.archive/"import/state.json")["status"]
                if status in {"finished","blocked","stopped"}:
                    self.update(LANE,status="finished",step="verified archive protocol queue drained")
                    return
                self.update(LANE,status="waiting",step="await more committed archive observations")
                time.sleep(45)
            else:
                time.sleep(4)
        self.update(LANE,status="stopped")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("root","repo","mi"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    r=ArchiveRunner(a.root,a.repo,a.mi)
    with (r.run/"executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("archive detail executor already running")
            return
        if r.state["lanes"].get(LANE,{}).get("inflight"):
            raise Blocked("unconfirmed writes; reconcile before retry")
        r.guarded(LANE,r.lane)


if __name__=="__main__":
    main()
