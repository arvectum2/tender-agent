"""Durable source-grounded ChatGPT review queue for MI-013.

ChatGPT conversation can act as reviewer when the owner triggers a run; this
queue does not pretend the chat session is a callable background API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .pq_chatgpt_review import prepare_packet, validate_review

STATES = frozenset({"pending_review", "reviewed"})


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".review-", suffix=".tmp", delete=False) as out:
        tmp = Path(out.name)
        json.dump(payload, out, ensure_ascii=False, indent=2)
        out.write("\n")
    os.replace(tmp, path)


def enqueue(*, source_dir: Path, ontology: Path, registry_number: str,
            queue_dir: Path, max_files: int = 8) -> dict:
    packet = prepare_packet(document_dir=source_dir, ontology_path=ontology,
                            registry_number=registry_number, max_files=max_files)
    digest = hashlib.sha256(json.dumps(
        [(d["filename"], d["sha256"]) for d in packet["documents"]],
        sort_keys=True).encode()).hexdigest()[:24]
    identity = f"{registry_number}-{digest}"
    path = queue_dir / f"{identity}.json"
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current["packet"]["documents"] != packet["documents"]:
            raise ValueError("Queue identity collision")
        return current
    item = {"schema_version": "pq-review-queue/1", "id": identity,
            "state": "pending_review", "packet": packet, "review": None}
    _atomic(path, item)
    return item


def accept(*, queue_dir: Path, identity: str, review: dict) -> dict:
    if not identity or any(c not in "0123456789-abcdef" for c in identity):
        raise ValueError("Invalid queue identity")
    path = queue_dir / f"{identity}.json"
    item = json.loads(path.read_text(encoding="utf-8"))
    if item["id"] != identity or item["state"] not in STATES:
        raise ValueError("Invalid queue record")
    verified = validate_review(packet=item["packet"], review=review)
    if item["state"] == "reviewed":
        if item["review"] != verified:
            raise ValueError("Immutable review conflict")
        return item
    item["review"] = verified
    item["state"] = "reviewed"
    _atomic(path, item)
    return item


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("enqueue")
    create.add_argument("--source-dir", type=Path, required=True)
    create.add_argument("--ontology", type=Path, required=True)
    create.add_argument("--registry-number", required=True)
    create.add_argument("--queue-dir", type=Path, required=True)
    accept_parser = sub.add_parser("accept")
    accept_parser.add_argument("--queue-dir", type=Path, required=True)
    accept_parser.add_argument("--id", required=True)
    accept_parser.add_argument("--review-json", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "enqueue":
        result = enqueue(source_dir=args.source_dir, ontology=args.ontology,
                         registry_number=args.registry_number, queue_dir=args.queue_dir)
    else:
        result = accept(queue_dir=args.queue_dir, identity=args.id,
                        review=json.loads(args.review_json.read_text(encoding="utf-8")))
    print(json.dumps({"id": result["id"], "state": result["state"]}))


if __name__ == "__main__":
    main()
