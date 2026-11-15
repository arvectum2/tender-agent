"""Durable executor for the approved public GPB and SIBUR research queues."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

PY = "/opt/homebrew/bin/python3"
MI_PY = "/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python"
API = "arvectum-local-e2e-api-1"
DB = "arvectum-local-e2e-db-1"
TASK = "TA-AUTONOMOUS-RESEARCH-RUNNER-20261115"
STATS = """import os,json
from arvectum_data_client import DataPlatformClient
with DataPlatformClient(base_url=os.environ['AI_CORP_RAG_DATA_PLATFORM_BASE_URL'],api_key=os.environ['AI_CORP_RAG_DATA_PLATFORM_API_KEY'],timeout_seconds=15) as c:
 s=c.collection_stats('tender-agent:sibur-public-research')
 print(json.dumps({k:s[k] for k in ('documents','chunks','embeddings')}))
"""


def utc():
    return datetime.now(UTC).isoformat()


def read(path):
    return json.loads(path.read_text())


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + ".partial")
    with tmp.open("w") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def planned(output, key):
    match = re.search(rf"^{key} (\d+)(?: |$)", output, re.MULTILINE)
    if not match:
        raise ValueError(f"missing {key} counter")
    return int(match[1])


class Blocked(RuntimeError):
    pass


class Runner:
    def __init__(self, root, gpb, sibur, mi):
        self.root, self.gpb, self.sibur, self.mi = root, gpb, sibur, mi
        self.run = root / "autonomous-runner"
        self.run.mkdir(mode=0o700, exist_ok=True)
        self.state_path = self.run / "state.json"
        self.state = read(self.state_path) if self.state_path.exists() else {
            "task_id": TASK, "created_at": utc(), "lanes": {}}
        self.mutex = threading.Lock()
        self.write_mutex = threading.Lock()
        self.gpb_root = root / "parallel-sources"
        self.docs = root / "documents"
        self.last_link_input = self.docs / "verified-ta-link-input-138.json"

    def record_heads(self):
        with self.mutex:
            heads = {name: subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo,
                                                  timeout=10, text=True).strip()
                     for name, repo in (("gpb", self.gpb), ("sibur", self.sibur), ("mi", self.mi))}
            self.state.update(heads=heads, pid=os.getpid(), started_at=utc(), updated_at=utc())
            atomic(self.state_path, self.state)

    def update(self, lane, **values):
        with self.mutex:
            entry = self.state["lanes"].setdefault(lane, {})
            entry.update(values, updated_at=utc())
            self.state.update(updated_at=utc(), pid=os.getpid())
            atomic(self.state_path, self.state)

    def stop_requested(self):
        return (self.run / "STOP").exists()

    def cmd(self, lane, step, args, cwd, timeout=120, data=None):
        self.update(lane, status="running", step=step, deadline_seconds=timeout)
        try:
            result = subprocess.run(args, cwd=cwd, input=data, capture_output=True,
                                    timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise Blocked(f"{step}: timeout; reconcile before retry") from exc
        with (self.run / f"{lane}.log").open("ab") as log:
            log.write(f"\n{utc()} {step} exit={result.returncode}\n".encode())
            if step not in {"link_gpb_document_receipts", "persist_gpb_protocol_decisions"} or result.returncode:
                log.write(result.stdout[-12000:] + result.stderr[-4000:])
        if result.returncode:
            raise Blocked(f"{step}: exit {result.returncode}; see private log")
        return result.stdout

    def module(self, lane, repo, name, *args, timeout=120):
        return self.cmd(lane, name, [PY, "-m", "scripts.research." + name, *map(str, args)], repo, timeout)

    @contextmanager
    def mutation_guard(self):
        with self.write_mutex, (self.run / "mutation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def gate(self, lane):
        if shutil.disk_usage(self.root).free < 15 * 1024**3:
            raise Blocked("runtime disk safety threshold reached")
        self.cmd(lane, "MI backup", [MI_PY, "-m", "scripts.market_intelligence.backup_pq_postgres"], self.mi, 150)
        raw = self.cmd(lane, "MI runtime gate", [MI_PY, "-m", "scripts.market_intelligence.verify_internal_runtime"], self.mi, 150)
        gate = json.loads(raw)
        if gate["status"] != "pass" or not gate.get("backup", {}).get("sha256"):
            raise Blocked("MI gate failed")
        path = self.run / f"{lane}-gate.json"
        atomic(path, gate)
        return path

    def backup_ta(self, lane):
        path = self.run / "backups"
        path.mkdir(mode=0o700, exist_ok=True)
        name = path / (lane + "-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".dump")
        self.update(lane, step="TA verified backup", deadline_seconds=220)
        partial = name.with_suffix(".partial")
        with partial.open("xb") as f:
            subprocess.run(["docker", "exec", DB, "sh", "-c",
                            'exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl'],
                           stdout=f, stderr=subprocess.PIPE, timeout=180, check=True)
            f.flush()
            os.fsync(f.fileno())
        if not partial.stat().st_size:
            raise Blocked("empty backup")
        subprocess.run(["/opt/homebrew/opt/postgresql@16/bin/pg_restore", "-l", str(partial)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=40, check=True)
        partial.replace(name)
        with name.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        self.update(lane, last_backup=name.name, last_backup_sha256=digest)

    def importer(self, lane, repo, name, data):
        code = (repo / "scripts" / "research" / (name + ".py")).read_text()
        return json.loads(self.cmd(lane, name, ["docker", "exec", "-i", API, "python", "-c", code],
                                   repo, 180, data))

    def gpb_sync(self, stage):
        lane = "gpb"
        folder = self.gpb_root / stage
        links = self.module(lane, self.gpb, "link_gpb_document_receipts", "--prepare", folder, timeout=120)
        decisions = self.module(lane, self.gpb, "persist_gpb_protocol_decisions", "--prepare", folder, timeout=120)
        fingerprint = hashlib.sha256(links + decisions).hexdigest()
        key = stage + "_sync_sha"
        if self.state["lanes"][lane].get(key) == fingerprint:
            return
        with self.mutation_guard():
            self.gate(lane)
            self.backup_ta(lane)
            linked = self.importer(lane, self.gpb, "link_gpb_document_receipts", links)
            outcomes = self.importer(lane, self.gpb, "persist_gpb_protocol_decisions", decisions)
            repeat = self.importer(lane, self.gpb, "persist_gpb_protocol_decisions", decisions)
            if repeat["updated"]:
                raise Blocked("decision replay not idempotent")
        self.update(lane, **{key: fingerprint, stage + "_links": linked, stage + "_outcomes": outcomes})

    def gpb_lane(self):
        lane = "gpb"
        active = self.gpb_root / "active-priority-details"
        hist = self.gpb_root / "historical-priority-details"
        while not self.stop_requested():
            if shutil.disk_usage(self.root).free < 15 * 1024**3:
                raise Blocked("runtime disk safety threshold reached")
            details = self.module(lane, self.gpb, "capture_gpb_priority_details", "--root", self.gpb_root,
                                  "--stage", "completed", "--limit", 30, timeout=420).decode()
            protocols = self.module(lane, self.gpb, "acquire_gpb_documents", "--root", hist,
                                    "--limit", 30, "--include-archives", "--protocols-only", timeout=650).decode()
            self.gpb_sync("historical-priority-details")
            active_docs = self.module(lane, self.gpb, "acquire_gpb_documents", "--root", active,
                                      "--limit", 20, "--include-archives", timeout=480).decode()
            self.gpb_sync("active-priority-details")
            self.update(lane, historical_details=len(read(hist / "receipts.json")),
                        historical_capture_receipts=len(read(hist / "document-pilot-receipts.json")),
                        active_capture_receipts=len(read(active / "document-pilot-receipts.json")),
                        cycles=self.state["lanes"][lane].get("cycles", 0) + 1)
            if not any(planned(output, "attempted") for output in (details, protocols, active_docs)):
                extra = self.module(lane, self.gpb, "acquire_gpb_documents", "--root", hist,
                                    "--limit", 30, "--include-archives", timeout=650).decode()
                self.gpb_sync("historical-priority-details")
                if not planned(extra, "attempted"):
                    self.update(lane, status="exhausted", step="verified snapshot queue drained; review exceptions and older history")
                    return
            time.sleep(1)
        self.update(lane, status="stopped", step="operator STOP")

    def local_index(self):
        index = {}
        for file in self.docs.glob("persistent-pilot-*.json"):
            r = read(file)
            sha, result = r["source_sha256"], r["result"]
            if result["canonical_uri"] != "content-sha256://" + sha or not result["embeddings"]:
                raise Blocked("invalid local index receipt")
            index[sha] = result
        # Recovered resources have a distinct read-only per-chunk attestation,
        # not a fabricated HTTP ingest response.
        recovered = json.loads(subprocess.check_output(
            [PY, "-m", "scripts.research.reconciled_sibur_index", str(self.docs)],
            cwd=self.sibur, timeout=60))
        if set(index) & set(recovered):
            raise Blocked("source has both HTTP and reconciliation receipts")
        index.update(recovered)
        return index

    def reconcile_index(self, index):
        stats = json.loads(self.cmd("sibur", "DP collection stats",
                           ["docker", "exec", API, "python", "-c", STATS], self.sibur, 30))
        recovered = read(self.docs / "dp-recovered-server-resource.json")
        legacy = recovered["source_sha256"] not in index
        expected = {"documents": len(index) + int(legacy),
                    "chunks": sum(r["chunks"] for r in index.values()) + (recovered["chunks"] if legacy else 0),
                    "embeddings": sum(r["embeddings"] for r in index.values()) + (recovered["chunks"] if legacy else 0)}
        if stats != expected:
            raise Blocked("DP receipt/aggregate discrepancy; reconcile exact server identities before retry")
        self.update("sibur", server=stats, full_receipts=len(index))

    def sibur_sync(self, index):
        payload = read(self.last_link_input)
        payload["indexed"] = index
        linked = self.importer("sibur", self.sibur, "link_sibur_document_receipts",
                               json.dumps(payload, ensure_ascii=False).encode())
        self.update("sibur", last_links=linked)

    def sibur_lane(self):
        lane = "sibur"
        if self.state["lanes"].get(lane, {}).get("index_inflight"):
            raise Blocked("previous ingest interrupted before reconciliation; review exact DP resources")
        args = ["--snapshot", self.root / "sibur-full-sweep-v2", "--directory", self.docs,
                "--priority-queue", self.root / "sibur-preliminary-priority-queue.json"]
        for cap in (8, 12, 20, 40, 100):
            while not self.stop_requested():
                with self.mutation_guard():
                    before = self.local_index()
                    self.reconcile_index(before)
                    # Close any receipt-to-TA linkage gap from a prior failed response
                    # before submitting a new ingest.
                    if self.state["lanes"][lane].get("synced_count") != len(before):
                        self.gate(lane)
                        self.backup_ta(lane)
                        self.sibur_sync(before)
                        self.update(lane, synced_count=len(before))
                    gate = self.gate(lane)
                    error = None
                    self.update(lane, index_inflight=True, index_baseline=len(before))
                    try:
                        out = self.module(lane, self.sibur, "process_sibur_document_batch", *args,
                                          "--mode", "index", "--limit", 5, "--max-chunks", cap,
                                          "--formats", "docx", "xlsx", "pptx",
                                          "--prewrite-receipt", gate, "--request-timeout", 120, timeout=680).decode()
                    except Blocked as exc:
                        error = exc
                    after = self.local_index()
                    self.reconcile_index(after)
                    if not error:
                        self.update(lane, index_inflight=False)
                    if after != before or self.state["lanes"][lane].get("synced_count") != len(after):
                        self.gate(lane)
                        self.backup_ta(lane)
                        self.sibur_sync(after)
                        self.update(lane, synced_count=len(after))
                    if error:
                        raise error
                    count = planned(out, "planned")
                    if count == 0:
                        break
                    if len(after) <= len(before):
                        raise Blocked("index batch reported work without new receipts")
                self.update(lane, cycles=self.state["lanes"][lane].get("cycles", 0) + 1, chunk_cap=cap)
                time.sleep(1)
            if self.stop_requested():
                self.update(lane, status="stopped", step="operator STOP")
                return
        self.update(lane, status="exhausted", step="supported pre-extracted OOXML index queue drained; PDF/legacy review remains")

    def guarded(self, lane, callback):
        if self.state["lanes"].get(lane, {}).get("status") in {"blocked", "exhausted"}:
            return
        try:
            self.update(lane, status="running", step="resume from receipts", error=None)
            callback()
        except Exception as exc:  # noqa: BLE001 - lane isolation must record unexpected faults
            self.update(lane, status="blocked", error_type=type(exc).__name__,
                        error=str(exc)[:300] if isinstance(exc, Blocked) else "see private logs; operator review required")
            with (self.run / f"{lane}.log").open("a") as log:
                log.write(f"\n{utc()} blocked: {type(exc).__name__}\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "gpb", "sibur", "mi"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    os.umask(0o077)
    folder = args.root / "autonomous-runner"
    folder.mkdir(mode=0o700, exist_ok=True)
    with (folder / "executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Executor already running")
            return
        r = Runner(args.root, args.gpb, args.sibur, args.mi)
        r.record_heads()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(r.guarded, "gpb", r.gpb_lane),
                    pool.submit(r.guarded, "sibur", r.sibur_lane)]
            for job in jobs:
                job.result()


if __name__ == "__main__":
    main()
