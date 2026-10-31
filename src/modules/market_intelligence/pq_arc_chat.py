"""ARC ↔ current ChatGPT conversation handoff, without API or local LLM.

The assistant reads source-bound queue packets via ARC, reasons in the current
conversation and submits an evidence-grounded JSON decision via ARC.
This is an interactive orchestration contract, not an unattended model daemon.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pq_review_queue import accept

MAX_DISPLAY_CHARS = 12000


def next_packet(*, queue_dir: Path, max_chars: int = MAX_DISPLAY_CHARS) -> dict:
    if not 1000 <= max_chars <= MAX_DISPLAY_CHARS or queue_dir.is_symlink():
        raise ValueError("Invalid ARC handoff budget")
    unreadable = 0
    duplicates = 0
    records = []
    reviewed = {}
    for path in sorted(queue_dir.glob("*.json")):
        if path.is_symlink():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("schema_version") != "pq-review-queue/1":
            continue
        records.append(item)
        if item.get("state") == "reviewed" and item.get("review"):
            packet = item.get("packet") or {}
            key = str(packet.get("registry_number") or "")
            shas = {d.get("sha256") for d in packet.get("documents", [])}
            if key and shas and None not in shas:
                reviewed.setdefault(key, []).append(shas)
    for item in records:
        if item.get("state") != "pending_review":
            continue
        packet = item["packet"]
        sha_set = {d.get("sha256") for d in packet["documents"]}
        if sha_set and None not in sha_set and any(
                sha_set <= old for old in reviewed.get(packet["registry_number"], [])):
            duplicates += 1
            continue
        if not any(len(" ".join(d.get("text", "").split())) >= 12 for d in packet["documents"]):
            unreadable += 1
            continue
        docs = []
        remaining = max_chars
        for index, document in enumerate(packet["documents"]):
            if remaining <= 0:
                break
            fair_share = max(1, remaining // (len(packet["documents"]) - index))
            snippet = document["text"][:fair_share]
            remaining -= len(snippet)
            docs.append({
                "filename": document["filename"],
                "sha256": document["sha256"],
                "text": snippet,
                "text_excerpt_only": len(snippet) < len(document["text"]),
                "lexical_hints_only": document.get("lexical_hints_only", []),
            })
        return {
            "status": "pending",
            "id": item["id"],
            "registry_number": packet["registry_number"],
            "documents": docs,
            "review_schema": {
                "registry_number": "same as packet",
                "classification": "relevant | irrelevant | uncertain",
                "evidence": [{"sha256": "exact document SHA", "quote": "exact source quote >=12 chars"}],
                "reasoning": "grounded equipment and procurement scope",
            },
            "reviewer": "current_chatgpt_conversation_via_arc",
        }
    return {"status": "empty", "reviewer": "current_chatgpt_conversation_via_arc",
            "pending_unreadable": unreadable,
            "pending_exact_sha_duplicates_skipped": duplicates}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    nxt = sub.add_parser("next")
    nxt.add_argument("--queue-dir", type=Path, required=True)
    nxt.add_argument("--max-chars", type=int, default=MAX_DISPLAY_CHARS)
    done = sub.add_parser("accept")
    done.add_argument("--queue-dir", type=Path, required=True)
    done.add_argument("--id", required=True)
    done.add_argument("--review-json", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "next":
        print(json.dumps(next_packet(queue_dir=args.queue_dir, max_chars=args.max_chars),
                         ensure_ascii=False))
    else:
        review = json.loads(args.review_json.read_text(encoding="utf-8"))
        result = accept(queue_dir=args.queue_dir, identity=args.id, review=review)
        print(json.dumps({"id": result["id"], "state": result["state"]}))


if __name__ == "__main__":
    main()
