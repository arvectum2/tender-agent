"""Recover only the terminal blocked GPB lane without interrupting active SIBUR indexing."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

from scripts.research.autonomous_runner import Blocked, Runner, atomic, read
from scripts.research.gpb_delta_sync import db_snapshot, plan, verify_plan_empty

EXPECTED_ERROR = "persist_gpb_protocol_decisions: exit 1; see private log"


class Recovery(Runner):
    def __init__(self, root, repo, mi):
        self.parent = root / "autonomous-runner"
        super().__init__(root, repo, repo, mi)
        self.run = self.parent / "gpb-recovery"
        self.run.mkdir(mode=0o700, exist_ok=True)
        self.state_path = self.run / "state.json"
        self.state = read(self.state_path) if self.state_path.exists() else {
            "task_id": "TA-GPB-BLOCKED-LANE-RECOVERY-20261115", "lanes": {}
        }

    @contextmanager
    def mutation_guard(self):
        with (self.parent / "mutation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def stop_requested(self):
        self.parent_blocked()
        return (self.run / "STOP").exists() or (self.parent / "STOP").exists()

    def parent_blocked(self):
        lane = read(self.parent / "state.json")["lanes"]["gpb"]
        if lane.get("status") != "blocked" or lane.get("error") != EXPECTED_ERROR:
            raise Blocked("parent lane no longer in known terminal blocked state")
        return lane

    def gpb_sync(self, stage):
        lane = "gpb"
        folder = self.gpb_root / stage
        links = self.module(lane, self.gpb, "link_gpb_document_receipts", "--prepare", folder, timeout=180)
        decisions = self.module(lane, self.gpb, "persist_gpb_protocol_decisions", "--prepare", folder, timeout=180)
        fingerprint = hashlib.sha256(links + decisions).hexdigest()
        key = stage + "_sync_sha"
        if self.state["lanes"][lane].get(key) == fingerprint:
            return
        all_links, all_decisions = json.loads(links), json.loads(decisions)
        with self.mutation_guard():
            ldelta, ddelta = plan(all_links, all_decisions, db_snapshot())
            self.update(lane, step="source-bound delta reconciliation",
                        pending_links=len(ldelta), pending_decisions=len(ddelta))
            linked = {"inserted": 0, "verified_links": len({(r["external_id"],r["sha256"]) for r in all_links}),
                      "verified_url_receipts": len(all_links)}
            outcomes = {"updated": 0, "verified": len(all_decisions)}
            if ldelta or ddelta:
                self.gate(lane)
                self.backup_ta(lane)
                self.update(lane, inflight=True, pending_sha=fingerprint)
                if ldelta:
                    linked["inserted"] = self.importer(lane, self.gpb, "link_gpb_document_receipts", json.dumps(ldelta).encode())["inserted"]
                if ddelta:
                    outcomes["updated"] = self.importer(lane, self.gpb, "persist_gpb_protocol_decisions", json.dumps(ddelta).encode())["updated"]
                verify_plan_empty(all_links, all_decisions, db_snapshot())
                atomic(self.run / ("delta-"+fingerprint+".json"), {"links":linked,"outcomes":outcomes,"verified_pending_after":0})
                self.update(lane, inflight=False)
            self.update(lane, **{key:fingerprint, stage+"_links":linked, stage+"_outcomes":outcomes})

    def lane(self):
        prior = self.parent_blocked()
        state = self.state["lanes"]["gpb"]
        if state.get("inflight"):
            raise Blocked("prior recovery write unconfirmed; reconcile first")
        if not state.get("parent_failure_recorded"):
            atomic(self.run / "parent-failure.json", prior)
            self.update("gpb", parent_failure_recorded=True)
        # Sync captured but not yet committed decisions before further collection.
        self.gpb_sync("historical-priority-details")
        self.parent_blocked()
        super().gpb_lane()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "repo", "mi"):
        p.add_argument("--"+name, type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    r = Recovery(a.root, a.repo, a.mi)
    with (r.run / "executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("GPB recovery already running")
            return
        r.parent_blocked()
        r.guarded("gpb", r.lane)


if __name__ == "__main__":
    main()
