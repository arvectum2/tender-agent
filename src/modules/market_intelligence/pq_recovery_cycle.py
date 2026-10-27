"""Bounded restartable PQ evidence recovery cycle; no scheduler or model API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pq_gap_recovery import inventory
from .pq_source_recovery import run as search_eis
from .pq_indexed_recovery import recover_indexed
from .pq_queue_seed import seed
from .pq_dp_ingest import ingest
from .pq_verified_stage import stage
from .pq_etp_card_audit import audit as audit_etp


def run_cycle(*, leads: Path, source_roots: list[Path], archive_index: Path,
              runtime: Path, ontology: Path, dp_source: Path,
              max_cases: int = 8, network: bool = True, verified_reestr: Path | None = None,
              etp_queue: Path | None = None) -> dict:
    if not 1 <= max_cases <= 30 or not source_roots:
        raise ValueError("Invalid cycle scope")
    runtime.mkdir(parents=True, exist_ok=True)
    queue = runtime / "review-queue"
    originals = runtime / "recovered-originals"
    roots = [*source_roots, originals]
    staged = None
    if verified_reestr:
        staged = runtime / 'verified-official-originals'
        staging_result = stage(source_root=verified_reestr, output_root=staged, max_cases=max_cases)
        roots.append(staged)
    gaps = runtime / "evidence-gaps-cycle.json"
    report = {"schema_version": "pq-recovery-cycle/1", "network_enabled": network}
    if staged:
        report["verified_originals"] = staging_result
    report["inventory"] = inventory(leads_file=leads, source_roots=roots,
                                    queue_dir=queue, output=gaps)
    if network:
        report["official_search"] = search_eis(
            gaps=gaps, journal=runtime / "source-attempts.json",
            max_cases=max_cases)
        report["indexed_recovery"] = recover_indexed(
            index_path=archive_index, gaps_path=gaps, target_root=originals,
            journal=runtime / "indexed-recovery-attempts.json",
            max_cases=max_cases)
    else:
        report["official_search"] = {"status": "skipped_offline"}
        report["indexed_recovery"] = {"status": "skipped_offline"}
    if etp_queue is not None:
        report["etp_cards"] = (audit_etp(queue_file=etp_queue,
            journal=runtime / "etp-source-attempts.json",
            max_tasks=min(max_cases, 3)) if network else {"status": "skipped_offline"})
    report["review_queues"] = []
    for root in roots:
        if root.is_dir():
            report["review_queues"].append(seed(
                sources=root, ontology=ontology, queue_dir=queue,
                max_cases=max_cases))
    report["data_platform"] = (
        ingest(sources=originals, output=runtime / "dp-extracted.json",
               dp_source=dp_source, max_files=max_cases * 8, ocr_empty=True)
        if originals.is_dir() else {"files_inspected": 0, "status": "no_recovered_originals"})
    if staged:
        report["verified_data_platform"] = ingest(sources=staged, output=runtime / "dp-verified-official-extract.json", dp_source=dp_source, max_files=max_cases * 8, ocr_empty=True)
    (runtime / "last-recovery-cycle.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--source-root", type=Path, action="append", required=True)
    p.add_argument("--archive-index", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--ontology", type=Path, required=True)
    p.add_argument("--dp-source", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=8)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--verified-reestr", type=Path)
    p.add_argument("--etp-queue", type=Path)
    a = p.parse_args()
    result = run_cycle(leads=a.leads, source_roots=a.source_root,
                       archive_index=a.archive_index, runtime=a.runtime,
                       ontology=a.ontology, dp_source=a.dp_source,
                       max_cases=a.max_cases, network=not a.offline, verified_reestr=a.verified_reestr, etp_queue=a.etp_queue)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
