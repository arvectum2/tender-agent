"""Bounded, resumable Power Quality evidence recovery cycle.

Uses official EIS search and original-document queues. No local/API LLM,
ETP mutation, signed-award inference, or automatic Data Platform ingestion.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .pq_arc_chat import next_packet
from .pq_gap_recovery import inventory
from .pq_queue_seed import seed
from .pq_run_lease import acquire, inspect, release
from .pq_source_recovery import run as source_search


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".cycle-", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def cycle(*, leads_file: Path, source_roots: list[Path], ontology: Path,
          queue_dir: Path, output_dir: Path, max_cases: int = 8,
          live_search: bool = False) -> dict:
    if not 1 <= max_cases <= 20 or not source_roots:
        raise ValueError("Invalid bounded cycle scope")
    if any(p.is_symlink() for p in (leads_file, ontology, queue_dir, output_dir, *source_roots)):
        raise ValueError("Symlinked cycle path")
    leads = json.loads(leads_file.read_text(encoding="utf-8"))
    if not isinstance(leads.get("records"), list) or not leads["records"]:
        raise ValueError("Materialized lead records required; manifest-only corpus not supported")
    if not all(root.is_dir() for root in source_roots):
        raise ValueError("Missing original source root")
    lease_path = output_dir / "watchdog-mi-lease"
    lease = acquire(lease_path, ttl_seconds=300)
    if lease is None:
        return {"status": "lease_blocked", "lease": inspect(lease_path),
                "no_mutation": True}
    try:
        gaps = output_dir / "evidence-gaps-expanded.json"
        inv = inventory(leads_file=leads_file, source_roots=source_roots,
                        queue_dir=queue_dir, output=gaps)
        search = (source_search(gaps=gaps, journal=output_dir / "source-attempts.json",
                                max_cases=max_cases)
                  if live_search else {"status": "not_attempted",
                                       "reason": "live_search_disabled"})
        seeded = [seed(sources=root, ontology=ontology, queue_dir=queue_dir,
                       max_cases=max_cases) for root in source_roots]
        pending = next_packet(queue_dir=queue_dir, max_chars=6000)
        result = {
            "schema_version": "pq-recovery-cycle/1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "completed_bounded_cycle",
            "lead_scope": str(leads_file),
            "lead_count": inv["lead_count"],
            "inventory": inv,
            "official_notice_search": search,
            "queue_seed": [
                {"source_root": row["source_root"], "created": row["created"],
                 "existing": row["existing"], "skipped_count": len(row["skipped"]),
                 "errors": row["errors"]} for row in seeded
            ],
            "pending_review": {"status": pending["status"], "id": pending.get("id")},
            "signed_contracts_verified_this_cycle": 0,
            "winners_verified_this_cycle": 0,
            "commercial_etp_search": "not_attempted_no_approved_adapter",
            "data_platform_ingestion": "not_attempted_no_new_reviewed_originals",
            "market_total_rub": None,
            "next_action": ("ChatGPT ARC review of pending source packet"
                            if pending["status"] == "pending"
                            else "Recover original signed outcomes and materialize wider corpus"),
        }
        _atomic_json(output_dir / "last_cycle.json", result)
        return result
    finally:
        if not release(lease):
            raise RuntimeError("Cooperative lease ownership changed; reconcile before next mutation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads-file", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, action="append", required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=8)
    parser.add_argument("--live-search", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cycle(leads_file=args.leads_file, source_roots=args.source_root,
                           ontology=args.ontology, queue_dir=args.queue_dir,
                           output_dir=args.output_dir, max_cases=args.max_cases,
                           live_search=args.live_search), ensure_ascii=False))


if __name__ == "__main__":
    main()
