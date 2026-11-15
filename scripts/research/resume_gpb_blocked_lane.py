"""Recover only the terminal blocked GPB lane without interrupting active SIBUR indexing."""
from __future__ import annotations

import argparse
import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

from scripts.research.autonomous_runner import Blocked, Runner, atomic, read

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
