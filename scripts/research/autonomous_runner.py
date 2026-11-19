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
ARCHIVE_INDEX_BATCH_SIZE = 10
ARCHIVE_INDEX_BATCH_TIMEOUT = 2050
FILE_REVIEW_CIRCUIT_LIMIT = 5
FILE_REVIEW_REASONS = {"CalledProcessError", "BadZipFile", "UnsupportedOriginalStructure"}
STATS = """import os,json
from arvectum_data_client import DataPlatformClient
with DataPlatformClient(base_url=os.environ['AI_CORP_RAG_DATA_PLATFORM_BASE_URL'],api_key=os.environ['AI_CORP_RAG_DATA_PLATFORM_API_KEY'],timeout_seconds=60) as c:
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


class FileReview(Blocked):
    """Explicit file-scoped failure from a bounded, trusted subprocess."""
    def __init__(self, step, mode, failures):
        self.step, self.mode, self.failures = step, mode, tuple(failures)
        super().__init__(f"{step}: file review required; see private log")


def classify_file_review(step, args, returncode, stdout):
    if returncode != 2 or step not in {
        "member_index_batch_extract", "member_index_batch_index", "archive_index_batch"
    }:
        return None
    try:
        words = list(map(str, args))
        mode = words[words.index("--mode") + 1]
        lines = stdout.decode("utf-8", errors="strict").splitlines()
    except (ValueError, IndexError, UnicodeError):
        return None
    if mode not in {"extract", "index"}:
        return None
    if step.startswith("member_") and step != "member_index_batch_" + mode:
        return None
    review = [line for line in lines if " review " in line]
    if not 1 <= len(review) <= 2:
        return None
    pairs = []
    for line in review:
        match = re.fullmatch(r"([0-9a-f]{12}) review ([A-Za-z]+)", line)
        if not match or match[2] not in FILE_REVIEW_REASONS:
            return None
        pairs.append((match[1], match[2]))
    if len({prefix for prefix, _ in pairs}) != len(pairs):
        return None
    return FileReview(step, mode, pairs)


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
        self.member_plan = None
        self.member_plan_sha = None
        self.member_queue = False
        self.member_batch_limit = 3
        self.archive_refresh_retry_at = 0.0

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
            review = classify_file_review(step, args, result.returncode, result.stdout)
            if review is not None and lane == "sibur":
                raise review
            raise Blocked(f"{step}: exit {result.returncode}; see private log")
        return result.stdout

    def module(self, lane, repo, name, *args, timeout=120):
        return self.cmd(lane, name, [PY, "-m", "scripts.research." + name, *map(str, args)], repo, timeout)

    @contextmanager
    def mutation_guard(self):
        # A fresh-public importer holds the exclusive priority lease before
        # waiting for mutation.lock. Never wait for priority while holding
        # mutation. Kernel locks are automatically released on process exit.
        with self.write_mutex, (self.run / "mutation.lock").open("a") as lock, (self.run / "fresh-procurement-priority.lock").open("a") as priority:
            while True:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    fcntl.flock(priority, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    if self.stop_requested():
                        raise Blocked("STOP while waiting for priority procurement writer")
                    time.sleep(2)
                    continue
                fcntl.flock(priority, fcntl.LOCK_UN)
                try:
                    yield
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                return

    def gate(self, lane):
        if shutil.disk_usage(self.root).free < 15 * 1024**3:
            raise Blocked("runtime disk safety threshold reached")
        self.cmd(lane, "MI backup", [MI_PY, "-m", "scripts.market_intelligence.backup_pq_postgres"], self.mi, 330)
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
                           ["docker", "exec", API, "python", "-c", STATS], self.sibur, 80))
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
        if self.state["lanes"][lane].get("archive_bridge_sha256"):
            self.archive_index_lane()
            return
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
                                          "--prewrite-receipt", gate, "--request-timeout", 180, timeout=1050).decode()
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
        self.archive_index_lane()

    def refresh_archive_bridge(self, lane, bridge, digest):
        """Called under executor and mutation locks, with reconciled receipts."""
        before = bridge.read_bytes()
        if hashlib.sha256(before).hexdigest() != digest:
            raise Blocked("archive bridge changed before refresh")
        result = json.loads(self.module(lane, self.sibur, "refresh_sibur_archive_index",
                                        "--root", self.root, "--digest", digest, timeout=600))
        if result["prior_digest"] != digest or result["indexed_count"] != len(self.local_index()):
            raise Blocked("archive refresh baseline changed")
        count = result["new_ready"]
        reviews = result.get("new_review", 0)
        if not count and not result.get("file"):
            self.update(lane, archive_refresh=result)
            return None
        if type(count) is not int or type(reviews) is not int or min(count,reviews)<0 or not 1 <= count+reviews <= 160:
            raise Blocked("archive refresh exceeds bound")
        path = bridge.parent / result["file"]
        if path.parent != bridge.parent or not re.fullmatch(r"archive-index-bridge-auto-[0-9]{8}T[0-9]{12}Z\.json", path.name) or path.is_symlink():
            raise Blocked("invalid prepared bridge path")
        raw = path.read_bytes()
        new_digest = hashlib.sha256(raw).hexdigest()
        old, new = json.loads(before), json.loads(raw)
        n = len(old["ready"])
        if (new_digest != result["digest"] or new["schema"] != old["schema"]
                or new["ready"][:n] != old["ready"] or len(new["ready"]) != n + count
                or new["review"][:len(old["review"])] != old["review"]
                or len(new["review"]) != len(old["review"])+reviews):
            raise Blocked("prepared bridge identity mismatch")
        added = [r["sha256"] for r in new["ready"][n:]]
        if len(set(added)) != count or set(added) & ({r["sha256"] for r in old["ready"]} | set(self.local_index())):
            raise Blocked("duplicate archive refresh entry")
        if not count and not any(r["reason"]=="structure_review" for r in new["review"][len(old["review"]):]):
            raise Blocked("review-only refresh without structural progress")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        saved = bridge.parent / ("archive-index-bridge-before-auto-" + stamp + ".json")
        state_saved = self.run / ("state-before-auto-refresh-" + stamp + ".json")
        for target, data in ((saved, before), (state_saved, self.state_path.read_bytes())):
            with target.open("xb") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
        # A crash between the two atomic replacements fails closed on digest
        # mismatch at the next launch. The immutable prepared and prior files
        # remain available for explicit reconciliation.
        tmp = bridge.with_suffix(".refresh-partial")
        with tmp.open("xb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        tmp.replace(bridge)
        self.update(lane, archive_bridge_sha256=new_digest,
                    archive_refresh={**result, "prior_bridge": saved.name,
                                     "prior_state": state_saved.name})
        return new_digest, new["ready"]

    def refresh_archive_when_due(self, lane, bridge, digest):
        """An optional preparation-only scan must not starve verified members.

        A timeout cannot activate a bridge: refresh_sibur_archive_index only
        prepares a separate file. Recheck the actual active digest, exact
        receipt totals and absence of an inflight write before deferring it.
        Any other failure remains fail-closed.
        """
        if time.monotonic() < self.archive_refresh_retry_at:
            return None
        try:
            result = self.refresh_archive_bridge(lane, bridge, digest)
        except Blocked as exc:
            if str(exc) != "refresh_sibur_archive_index: timeout; reconcile before retry":
                raise
            state = self.state["lanes"][lane]
            if state.get("index_inflight") is not False or hashlib.sha256(bridge.read_bytes()).hexdigest() != digest:
                raise
            index = self.local_index()
            if state.get("archive_synced_count") != len(index):
                raise
            self.reconcile_index(index)
            self.archive_refresh_retry_at = time.monotonic() + 900
            self.update(lane, step="archive refresh deferred; member queue available",
                        archive_refresh_deferred={"reason": "preparation timeout", "at": utc(), "retry_seconds": 900, "digest": digest})
            return None
        if result is None:
            self.archive_refresh_retry_at = time.monotonic() + 900
        else:
            self.archive_refresh_retry_at = 0.0
        return result

    def defer_file_reviews(self, error, plan_path, digest, kind, index, new_receipts):
        """Under the mutation guard, after receipt reconciliation; no DB writes."""
        lane = "sibur"
        if not isinstance(error, FileReview) or kind not in {"member", "archive"}:
            raise Blocked("unclassified file failure")
        if plan_path.is_symlink() or hashlib.sha256(plan_path.read_bytes()).hexdigest() != digest:
            raise Blocked("review plan integrity mismatch")
        if self.state["lanes"][lane].get("archive_synced_count") != len(index):
            raise Blocked("review requires synchronized index")
        plan = read(plan_path)
        expected = "sibur_member_index_plan_v1" if kind == "member" else "sibur_archive_index_bridge_v1"
        if plan.get("schema") != expected:
            raise Blocked("review plan schema mismatch")
        base = self.root / "sibur-archive-expansion-v86"
        registry_path = base / "member-index-registry-v1.json"
        registry = read(registry_path)["rows"] if registry_path.exists() else {}
        records = {}
        for prefix, reason in error.failures:
            candidates = [row for row in plan["ready"] if row["sha256"].startswith(prefix)]
            if len(candidates) != 1:
                raise Blocked("failed file identity ambiguous")
            row = candidates[0]; h = row["sha256"]
            if not re.fullmatch(r"[0-9a-f]{64}", h) or h in index or h in registry or reason not in FILE_REVIEW_REASONS:
                raise Blocked("failed file already indexed or identity unverified")
            if kind == "member":
                if row["folder"] not in {"committed-members", "nested-members", "deep-members"}:
                    raise Blocked("failed member source folder mismatch")
                folder, size = base / row["folder"], row["bytes"]
            else:
                folder, size = self.root / "sibur-archive-discovery/categories/documents", row["size_bytes"]
            source = folder / row["file"]; staged = self.docs / row["file"]
            if source.parent != folder or staged.parent != self.docs or source.stem != h:
                raise Blocked("failed file path mismatch")
            for path in (source, staged):
                if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
                    raise Blocked("failed file missing or size mismatch")
                with path.open("rb") as f:
                    if hashlib.file_digest(f, "sha256").hexdigest() != h:
                        raise Blocked("failed file content hash mismatch")
            preflight = self.docs / (row["file"] + ".dp-result.json")
            records[h] = {
                "sha256": h, "reason": "auto_deferred_file_processing_failure",
                "error_class": reason, "phase": error.mode, "scope": kind,
                "source": str(source.relative_to(self.root)), "source_bytes": size,
                "source_preserved": True, "review_required": True,
                "attempts": 1, "deferred_at": utc(), "plan_sha256": digest,
                "plan_file": plan_path.name, "private_log": "autonomous-runner/sibur.log",
                "preflight_file": preflight.name if preflight.is_file() else None,
            }
        # A transport error can also indicate an outage or late commit.
        # Health and exact absence are mandatory before deferring a source.
        for port in (8094, 8090):
            health = self.cmd(lane, "file review service health",
                              ["curl", "--noproxy", "*", "-fsS", "--max-time", "5",
                               f"http://127.0.0.1:{port}/health"], self.sibur, 10)
            if json.loads(health).get("status") != "ok":
                raise Blocked("file review service unhealthy")
        uris = ",".join("'content-sha256://" + h + "'" for h in records)
        sql = ("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "
               "SELECT coalesce(json_agg(r.canonical_uri),'[]'::json) FROM dp_resources r "
               "WHERE r.collection_id='tender-agent:sibur-public-research' AND r.canonical_uri IN (" + uris + "); ROLLBACK;")
        observed = self.cmd(lane, "file review exact DP absence",
                            ["docker", "exec", "arvectum-postgres", "psql", "-X", "-qAt", "-U", "arvectum",
                             "-d", "arvectum_data", "-v", "ON_ERROR_STOP=1", "-c", sql], self.sibur, 30)
        if json.loads(observed) != []:
            raise Blocked("failed file exists in DP; reconcile exact identity")
        self.reconcile_index(index)
        ledger = base / "member-index-queue-reviews-v1.json"
        prior = read(ledger) if ledger.exists() else {"schema": "sibur_member_queue_structural_reviews_v1", "rows": {}}
        if prior.get("schema") != "sibur_member_queue_structural_reviews_v1" or not isinstance(prior.get("rows"), dict):
            raise Blocked("review ledger schema mismatch")
        if any(not re.fullmatch(r"[0-9a-f]{64}", h) or row.get("sha256") != h
               for h, row in prior["rows"].items()):
            raise Blocked("review ledger identity mismatch")
        if set(records) & set(prior["rows"]):
            raise Blocked("deferred file returned to active queue")
        atomic(ledger, {**prior, "rows": {**prior["rows"], **records}})
        streak = 0 if new_receipts else self.state["lanes"][lane].get("file_review_failure_streak", 0) + 1
        self.update(lane, index_inflight=False, file_review_failure_streak=streak,
                    last_file_reviews=list(records.values()), file_review_total=len(prior["rows"]) + len(records))
        if streak >= FILE_REVIEW_CIRCUIT_LIMIT:
            raise Blocked("file review circuit breaker: repeated batches without successful index")
        return list(records)

    def member_index_pilot(self, sync):
        """Single opt-in bounded batch, under the existing mutation lock."""
        lane="sibur";state=self.state["lanes"][lane]
        if not self.member_plan or state.get("member_pilot_completed_sha256")==self.member_plan_sha:
            return False
        if self.stop_requested() or state.get("index_inflight"):
            return False
        if self.member_plan.is_symlink() or hashlib.sha256(self.member_plan.read_bytes()).hexdigest()!=self.member_plan_sha:
            raise Blocked("member plan identity mismatch")
        before=self.local_index();self.reconcile_index(before)
        if state.get("archive_synced_count")!=len(before):
            raise Blocked("member pilot requires synchronized direct receipts")
        gate=self.gate(lane)
        self.update(lane,index_inflight=True,index_baseline=len(before),member_pilot_status="in_progress",member_plan_sha256=self.member_plan_sha)
        args=["--root",self.root,"--plan",self.member_plan,"--digest",self.member_plan_sha]
        def batch(mode):
            return self.cmd(lane,"member_index_batch_"+mode,[MI_PY,"-m","scripts.research.member_index_batch",*map(str,args),"--mode",mode,"--gate",str(gate),"--limit",str(self.member_batch_limit)],self.sibur,2050).decode()
        error=None
        try:
            x=batch("extract");self.reconcile_index(self.local_index());y=batch("index")
        except Blocked as exc:error=exc
        after=self.local_index();self.reconcile_index(after)
        if after!=before:
            self.gate(lane);self.backup_ta(lane);sync(after)
            if self.state["lanes"][lane].get("archive_synced_count")!=len(after):
                raise Blocked("member pilot direct sync did not reconcile")
        # Reconcile and publish every successfully indexed member even when
        # a later member failed.  Only verified file-scoped failures may be deferred.
        cmd=[MI_PY,"-m","scripts.research.link_sibur_member_index",*map(str,args)]
        linked=json.loads(self.cmd(lane,"member registry",cmd,self.sibur,600))
        repeat=json.loads(self.cmd(lane,"member registry replay",cmd,self.sibur,600))
        if repeat["updated"] or any(repeat[k]!=linked[k] for k in ("members","procedure_member_pairs","source_links","registry_sha256")):
            raise Blocked("member registry replay mismatch")
        if error:
            self.update(lane,member_pilot_status="partial_reconciled_blocked",
                        member_partial_registry=linked,member_partial_registry_replay=repeat,
                        member_partial_new_receipts=len(after)-len(before))
            if not getattr(self, "member_queue", False) or not isinstance(error, FileReview):
                raise error
            deferred = self.defer_file_reviews(error, self.member_plan, self.member_plan_sha,
                                               "member", after, len(after)-len(before))
            self.update(lane, member_pilot_status="completed_with_file_review",
                        member_pilot_completed_sha256=self.member_plan_sha,
                        member_pilot={"extracted_planned": 0, "indexed_planned": len(after)-len(before),
                                      "new_receipts": len(after)-len(before), "deferred_count": len(deferred),
                                      "deferred_sha256": deferred, "registry": linked, "replay": repeat})
            return True
        if len(after)>len(before):
            self.update(lane, file_review_failure_streak=0)
        self.update(lane,index_inflight=False,member_pilot_status="completed",member_pilot_completed_sha256=self.member_plan_sha,member_pilot={"extracted_planned":planned(x,"planned"),"indexed_planned":planned(y,"planned"),"new_receipts":len(after)-len(before),"registry":linked,"replay":repeat})
        return True

    def member_queue_cycle(self, sync):
        """Select and process a fresh bounded queue from verified receipts."""
        if not self.member_queue or self.stop_requested():return False
        lane="sibur";state=self.state["lanes"][lane]
        if state.get("index_inflight"):raise Blocked("member queue has unreconciled ingest")
        result=json.loads(self.cmd(lane,"prepare member queue",[MI_PY,"-m","scripts.research.prepare_sibur_member_queue","--root",str(self.root),"--limit","10"],self.sibur,180))
        self.update(lane,member_queue=result)
        if not result.get("file"):
            if result.get("new_review",0):return True
            return False
        folder=self.root/"sibur-sales-map-20261115";p=folder/result["file"];digest=result["digest"]
        if p.parent!=folder or p.is_symlink() or not re.fullmatch(r"member-index-auto-[0-9]{8}T[0-9]{12}Z\.json",p.name) or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise Blocked("member queue plan identity mismatch")
        if state.get("member_pilot_completed_sha256")==digest:raise Blocked("member queue repeated completed plan")
        self.member_plan=p;self.member_plan_sha=digest;self.member_batch_limit=10
        try:
            if not self.member_index_pilot(sync):return False
            receipt=self.state["lanes"][lane]["member_pilot"]
            if not (receipt["extracted_planned"] or receipt["indexed_planned"] or receipt["registry"]["updated"] or receipt.get("deferred_count", 0)):raise Blocked("member queue made no progress")
            self.update(lane,member_queue_cycles=state.get("member_queue_cycles",0)+1,member_queue_last_receipt=receipt)
            return True
        finally:
            self.member_plan=None;self.member_plan_sha=None;self.member_batch_limit=3

    def archive_index_lane(self):
        lane="sibur"
        digest=self.state["lanes"][lane].get("archive_bridge_sha256")
        if not digest:
            self.update(lane,status="exhausted",step="legacy queue drained; archive bridge not activated")
            return
        bridge=self.root/"sibur-sales-map-20261115/archive-index-bridge-v1.json"
        raw=bridge.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise Blocked("archive bridge changed")
        rows=json.loads(raw)["ready"]
        def sync(index):
            selected=[r for r in rows if r["sha256"] in index]
            if not selected:return
            payload=json.dumps({"rows":selected,"indexed":{r["sha256"]:index[r["sha256"]] for r in selected}},ensure_ascii=False).encode()
            linked=self.importer(lane,self.sibur,"link_sibur_archive_index",payload)
            repeat=self.importer(lane,self.sibur,"link_sibur_archive_index",payload)
            if repeat["updated"] or repeat["verified_links"]!=linked["verified_links"]:raise Blocked("archive index link replay mismatch")
            self.update(lane,archive_indexed=len(selected),archive_links=linked,archive_synced_count=len(index))
        while not self.stop_requested():
            with self.mutation_guard():
                before=self.local_index();self.reconcile_index(before)
                if self.state["lanes"][lane].get("archive_synced_count")!=len(before):
                    self.gate(lane);self.backup_ta(lane);sync(before)
                gate=self.gate(lane)
                # Process_document may have side effects: keep the same gate and
                # reconcile the collection even after extraction transport failure.
                self.update(lane,index_inflight=True,index_baseline=len(before),archive_index_batch_size=ARCHIVE_INDEX_BATCH_SIZE)
                error=None
                try:
                    x=self.module(lane,self.sibur,"archive_index_batch","--root",self.root,"--digest",digest,"--mode","extract","--gate",gate,"--limit",ARCHIVE_INDEX_BATCH_SIZE,timeout=ARCHIVE_INDEX_BATCH_TIMEOUT).decode()
                    self.reconcile_index(self.local_index())
                    y=self.module(lane,self.sibur,"archive_index_batch","--root",self.root,"--digest",digest,"--mode","index","--gate",gate,"--limit",ARCHIVE_INDEX_BATCH_SIZE,"--cap",100,timeout=ARCHIVE_INDEX_BATCH_TIMEOUT).decode()
                except Blocked as exc:error=exc
                after=self.local_index();self.reconcile_index(after)
                if after!=before:
                    self.gate(lane);self.backup_ta(lane);sync(after)
                if error:
                    if not self.member_queue or not isinstance(error, FileReview):
                        raise error
                    self.defer_file_reviews(error, bridge, digest, "archive", after, len(after)-len(before))
                    drained = False
                else:
                    if len(after)>len(before):
                        self.update(lane, file_review_failure_streak=0)
                    drained = not planned(x,"planned") and not planned(y,"planned")
                self.update(lane,index_inflight=False,archive_cycles=self.state["lanes"][lane].get("archive_cycles",0)+1)
            if drained:
                # The archive collector is independent; when the fixed queue
                # drains, refresh from committed receipts rather than exit.
                while not self.stop_requested():
                    with self.mutation_guard():
                        self.reconcile_index(self.local_index())
                        refreshed = self.refresh_archive_when_due(lane, bridge, digest)
                        if refreshed:
                            digest, rows = refreshed
                            break
                        if self.member_index_pilot(sync):
                            continue
                        if self.member_queue_cycle(sync):
                            continue
                    collector = self.root / "sibur-archive-discovery/categories/documents/state.json"
                    if not self.member_queue and (not collector.exists() or read(collector).get("status") != "running"):
                        self.update(lane,status="exhausted",step="committed priority queue drained; collector not running; review remains")
                        return
                    self.update(lane,step="waiting for committed archive receipts",deadline_seconds=60)
                    # No database mutation lock or backup while waiting.
                    for _ in range(12):
                        if self.stop_requested():
                            break
                        time.sleep(5)
            time.sleep(1)
        self.update(lane,status="stopped",step="operator STOP")

    def resume_sibur_refresh(self):
        """Recover only the known pre-ingest refresh failure, under executor lock."""
        lane = "sibur"
        state = self.state["lanes"].get(lane, {})
        if (state.get("status") != "blocked"
                or state.get("step") != "refresh_sibur_archive_index"
                or state.get("error") != "refresh_sibur_archive_index: exit 1; see private log"
                or state.get("index_inflight") is not False
                or self.stop_requested()):
            raise Blocked("not an eligible pre-ingest refresh recovery")
        bridge = self.root / "sibur-sales-map-20261115/archive-index-bridge-v1.json"
        digest = state.get("archive_bridge_sha256")
        if not digest or hashlib.sha256(bridge.read_bytes()).hexdigest() != digest:
            raise Blocked("archive bridge changed before recovery")
        with self.mutation_guard():
            index = self.local_index()
            if state.get("archive_synced_count") != len(index):
                raise Blocked("unreconciled archive receipts before recovery")
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            saved = self.run / ("state-before-refresh-recovery-" + stamp + ".json")
            with saved.open("xb") as f:
                f.write(self.state_path.read_bytes()); f.flush(); os.fsync(f.fileno())
            try:
                self.reconcile_index(index)
                refreshed = self.refresh_archive_bridge(lane, bridge, digest)
                if refreshed is None:
                    raise Blocked("no verified refresh progress")
            except Exception as exc:
                self.update(lane, status="blocked", step="refresh_sibur_archive_index",
                            error="refresh recovery failed; review private log",
                            error_type=type(exc).__name__)
                raise
            self.update(lane, status="running", step="verified refresh recovery",
                        error=None, error_type=None, refresh_recovery_state=saved.name)

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
    p.add_argument("--resume-sibur-refresh", action="store_true", help="recover only a reconciled pre-ingest refresh failure")
    p.add_argument("--member-plan", type=Path)
    p.add_argument("--member-plan-sha256")
    p.add_argument("--member-queue", action="store_true", help="continuously process bounded source-bound member plans")
    args = p.parse_args()
    if args.member_queue and args.member_plan:p.error("choose a pilot or continuous queue")
    if bool(args.member_plan)!=bool(args.member_plan_sha256):p.error("member plan and digest must be supplied together")
    if args.member_plan and (args.member_plan.is_symlink() or not re.fullmatch(r"[a-f0-9]{64}",args.member_plan_sha256) or hashlib.sha256(args.member_plan.read_bytes()).hexdigest()!=args.member_plan_sha256):p.error("member plan identity mismatch")
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
        r.member_queue=args.member_queue
        r.member_plan=args.member_plan
        r.member_plan_sha=args.member_plan_sha256
        if args.resume_sibur_refresh:
            r.resume_sibur_refresh()
        r.record_heads()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(r.guarded, "gpb", r.gpb_lane),
                    pool.submit(r.guarded, "sibur", r.sibur_lane)]
            for job in jobs:
                job.result()


if __name__ == "__main__":
    main()
