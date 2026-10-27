"""Bounded ARC/ChatGPT handoff batch with cooperative lease and durable journal.

No model API. The scheduled ChatGPT invocation reads the returned packet and
submits its independently reasoned source-grounded decision through ARC.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .pq_arc_chat import next_packet
from .pq_review_queue import accept
from .pq_run_lease import acquire, inspect, release, renew


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8",
                                     prefix=".batch-", delete=False) as out:
        tmp = Path(out.name)
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def begin(*, queue_dir: Path, runtime_dir: Path, max_chars: int = 12000) -> dict:
    lease_path = runtime_dir / "arc-chat-lease"
    lease = acquire(lease_path)
    if lease is None:
        return {"status": "busy", "lease": inspect(lease_path)}
    try:
        result = next_packet(queue_dir=queue_dir, max_chars=max_chars)
        if result["status"] == "empty":
            release(lease)
            return result
        _write(runtime_dir / "arc-chat-active.json", {
            "owner": lease.owner, "id": result["id"], "state": "awaiting_chat_review"})
        return {**result, "lease_owner": lease.owner}
    except BaseException:
        release(lease)
        raise


def complete(*, queue_dir: Path, runtime_dir: Path, owner: str, identity: str,
             review: dict) -> dict:
    from .pq_run_lease import Lease
    lease = Lease(runtime_dir / "arc-chat-lease", owner)
    if not renew(lease):
        return {"status": "lease_lost", "lease": inspect(lease.path)}
    active_path = runtime_dir / "arc-chat-active.json"
    active = json.loads(active_path.read_text(encoding="utf-8"))
    if active.get("owner") != owner or active.get("id") != identity:
        raise ValueError("Active batch ownership mismatch")
    try:
        item = accept(queue_dir=queue_dir, identity=identity, review=review)
        _write(active_path, {"owner": owner, "id": identity, "state": "reviewed"})
        return {"status": "reviewed", "id": item["id"], "classification": item["review"]["classification"]}
    finally:
        release(lease)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("begin", "complete", "inspect"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--queue-dir", type=Path, required=True)
        cmd.add_argument("--runtime-dir", type=Path, required=True)
        if action == "complete":
            cmd.add_argument("--owner", required=True)
            cmd.add_argument("--id", required=True)
            cmd.add_argument("--review-json", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "begin":
        result = begin(queue_dir=args.queue_dir, runtime_dir=args.runtime_dir)
    elif args.action == "complete":
        result = complete(queue_dir=args.queue_dir, runtime_dir=args.runtime_dir,
                          owner=args.owner, identity=args.id,
                          review=json.loads(args.review_json.read_text(encoding="utf-8")))
    else:
        result = inspect(args.runtime_dir / "arc-chat-lease")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
