"""Run official-source attachment recovery using exact indexed XML provenance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eis_attachment_acquisition import acquire_223fz_eis_attachments
from .pq_archive_recovery import _atomic


def recover_indexed(*, index_path: Path, gaps_path: Path, target_root: Path,
                    journal: Path, max_cases: int = 8) -> dict:
    if not 1 <= max_cases <= 30:
        raise ValueError("Invalid budget")
    source = json.loads(index_path.read_text(encoding="utf-8"))
    if source.get("schema_version") != "pq-official-archive-index/1":
        raise ValueError("Invalid archive index")
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))["cases"]
    state = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {
        "schema_version": "pq-indexed-recovery/1", "attempts": []}
    tried = {x["procedure_id"] for x in state["attempts"]}
    current = []
    for case in gaps:
        number = str(case["procedure_id"])
        if len(current) >= max_cases:
            break
        if number in tried or number not in source["records"]:
            continue
        rows = source["records"][number]
        outcome = {"procedure_id": number, "indexed_sources": len(rows),
                   "status": "no_download", "downloaded_count": 0}
        # Multiple revisions/archives may exist. Each is reverified by the
        # original-source acquisition adapter before any download.
        for row in rows[:6]:
            try:
                result = acquire_223fz_eis_attachments(
                    registry_number=number, archive_path=Path(row["archive"]),
                    archive_sha256=row["sha256"], region=row["region"],
                    source_date=row["date"], target_dir=target_root / number,
                    max_attachments=8)
                outcome["status"] = str(result.get("status", "processed"))
                outcome["downloaded_count"] += int(result.get("downloaded_count", 0))
                if outcome["downloaded_count"]:
                    outcome["source_archive_sha256"] = row["sha256"]
                    break
            except (OSError, ValueError, RuntimeError) as exc:
                outcome["status"] = "source_error"
                outcome["error_type"] = type(exc).__name__
        current.append(outcome)
        state["attempts"].append(outcome)
        _atomic(journal, state)
    return {"cases_attempted": len(current),
            "documents_downloaded": sum(x["downloaded_count"] for x in current),
            "results": current}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--gaps", type=Path, required=True)
    p.add_argument("--target-root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=8)
    a = p.parse_args()
    print(json.dumps(recover_indexed(index_path=a.index, gaps_path=a.gaps,
                                     target_root=a.target_root, journal=a.journal,
                                     max_cases=a.max_cases), ensure_ascii=False))


if __name__ == "__main__":
    main()
