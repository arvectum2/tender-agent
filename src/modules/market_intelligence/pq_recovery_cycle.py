"""Bounded restartable PQ evidence recovery cycle; no scheduler or model API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pq_commission_candidate_audit import extract as extract_commission_candidates
from .pq_commission_fact_audit import verify as verify_commission_facts
from .pq_contract_outcome_audit import audit as audit_contracts
from .pq_contract_xml_index import scan as scan_contracts
from .pq_dp_ingest import ingest
from .pq_etp_card_audit import audit as audit_etp
from .pq_gap_recovery import inventory
from .pq_indexed_recovery import recover_indexed
from .pq_public_223_acquire import batch as fetch_public_223
from .pq_public_223_canonical import canonicalize as canonicalize_public_223
from .pq_public_223_direct import merge_direct
from .pq_public_223_expand import expand as expand_public_223
from .pq_public_dp_resume import run as resume_public_dp
from .pq_queue_seed import seed
from .pq_source_recovery import run as search_eis
from .pq_verified_stage import stage
from .pq_verified_zip_expand import expand
from .pq_zip_dp_resume import run as resume_zip_ingest


def run_cycle(*, leads: Path, source_roots: list[Path], archive_index: Path,
              runtime: Path, ontology: Path, dp_source: Path,
              max_cases: int = 8, network: bool = True, verified_reestr: Path | None = None,
              etp_queue: Path | None = None,
              contract_root: Path | None = None,
              contract_day_scan: Path | None = None,
              public223_source: Path | None = None,
              commission_facts: Path | None = None) -> dict:
    if not 1 <= max_cases <= 30 or not source_roots:
        raise ValueError("Invalid cycle scope")
    runtime.mkdir(parents=True, exist_ok=True)
    queue = runtime / "review-queue"
    originals = runtime / "recovered-originals"
    roots = [*source_roots, originals]
    staged = None
    zip_staged = None
    if verified_reestr:
        staged = runtime / 'verified-official-originals'
        staging_result = stage(source_root=verified_reestr, output_root=staged, max_cases=max_cases)
        roots.append(staged)
        zip_staged = runtime / "verified-zip-members"
        zip_expansion = expand(source_root=verified_reestr, output_root=zip_staged, max_cases=max_cases)
        roots.append(zip_staged)
    gaps = runtime / "evidence-gaps-cycle.json"
    report = {"schema_version": "pq-recovery-cycle/1", "network_enabled": network}
    if staged:
        report["verified_originals"] = staging_result
        report["verified_zip_members"] = zip_expansion
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
    if zip_staged:
        report["zip_data_platform"] = resume_zip_ingest(source_root=zip_staged, runtime=runtime, dp_source=dp_source, max_files=min(max_cases * 2, 48))
    if public223_source is not None:
        if network:
            report["public223_fetch"] = fetch_public_223(
                gaps=gaps, target_root=public223_source,
                journal=runtime / "public223-attempts.json",
                max_cases=min(max_cases, 2))
        else:
            report["public223_fetch"] = {"status": "skipped_offline"}
        if public223_source.is_dir():
            expanded = runtime / "public223-expanded"
            report["public223_expansion"] = expand_public_223(
                source_root=public223_source, output_root=expanded,
                max_cases=60, max_archives=120)
            canonical = runtime / "public223-canonical"
            report["public223_canonical"] = canonicalize_public_223(
                staged=expanded, output=canonical, max_files=500)
            report["public223_direct"] = merge_direct(
                source_root=public223_source, canonical=canonical,
                max_cases=35, max_files=200)
            report["public223_data_platform"] = resume_public_dp(
                source_root=canonical, runtime=runtime, dp_source=dp_source,
                max_files=min(max_cases * 3, 60))
            report["public223_review_source_tier"] = "public_eis_page_not_original_soap_xml"
            report["review_queues"].append(seed(
                sources=canonical, ontology=ontology, queue_dir=queue,
                max_cases=200))
            report["inventory_after_public223"] = inventory(
                leads_file=leads, source_roots=[*roots, canonical],
                queue_dir=queue, output=runtime / "evidence-gaps-with-public223.json")
    if contract_root is not None:
        contract_index_path = runtime / "contract-xml-evidence.json"
        contract_index = scan_contracts(contract_root, leads)
        contract_index_path.write_text(
            json.dumps(contract_index, ensure_ascii=False, indent=2), encoding="utf-8")
        contract_audit_path = runtime / "contract-outcome-audit.json"
        contract_audit = audit_contracts(
            leads_path=leads, contracts_path=contract_index_path,
            contract_root=contract_root, day_scan_path=contract_day_scan)
        contract_audit_path.write_text(
            json.dumps(contract_audit, ensure_ascii=False, indent=2), encoding="utf-8")
        candidates = extract_commission_candidates(
            outcome_path=contract_audit_path, queue_dir=queue)
        candidate_path = runtime / "commission-candidates.json"
        candidate_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        report["commission_candidates"] = {
            "source_quote_candidates": candidates["candidate_mentions"],
            "review_packets_examined": candidates["review_packets_examined"],
            "candidate_artifact": str(candidate_path),
            "supplier_verified": 0,
        }
        report["contract_register"] = {
            "records_matched": contract_audit["distinct_contract_lots_matched"],
            "rub_prices_verified": contract_audit["contract_lots_with_rub_price"],
            "signed_contracts_verified": contract_audit["signed_contracts_verified"],
            "suppliers_verified": contract_audit["suppliers_verified"],
            "outcome_audit": str(contract_audit_path),
            "source_index": str(contract_index_path),
        }
    if commission_facts is not None:
        verified_facts = verify_commission_facts(facts=commission_facts, queue=queue)
        verified_file = runtime / "verified-commission-facts.json"
        verified_file.write_text(
            json.dumps(verified_facts, ensure_ascii=False, indent=2), encoding="utf-8")
        report["commission_facts_verified"] = {
            "source_bound_facts": verified_facts["facts_accepted"],
            "signed_contracts_verified": verified_facts["verified_signed_contracts"],
            "artifact": str(verified_file),
        }
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
    p.add_argument("--contract-root", type=Path)
    p.add_argument("--contract-day-scan", type=Path)
    p.add_argument("--public223-source", type=Path)
    p.add_argument("--commission-facts", type=Path)
    a = p.parse_args()
    result = run_cycle(leads=a.leads, source_roots=a.source_root,
                       archive_index=a.archive_index, runtime=a.runtime,
                       ontology=a.ontology, dp_source=a.dp_source,
                       max_cases=a.max_cases, network=not a.offline, verified_reestr=a.verified_reestr, etp_queue=a.etp_queue,
                       contract_root=a.contract_root, contract_day_scan=a.contract_day_scan,
                       public223_source=a.public223_source,
                       commission_facts=a.commission_facts)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
