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
from .pq_verified_zip_expand import expand
from .pq_zip_dp_resume import run as resume_zip_ingest
from .pq_etp_card_audit import audit as audit_etp
from .pq_contract_xml_index import scan as scan_contracts
from .pq_contract_outcome_audit import audit as audit_contracts
from .pq_commission_candidate_audit import extract as extract_commission_candidates
from .pq_public_223_acquire import batch as fetch_public_223
from .pq_public_223_expand import expand as expand_public_223
from .pq_public_223_canonical import canonicalize as canonicalize_public_223
from .pq_public_dp_resume import run as resume_public_dp
from .pq_public_223_direct import merge_direct
from .pq_commission_fact_audit import verify as verify_commission_facts
from .pq_primary_etp_capture import batch as fetch_primary_etp
from .pq_primary_etp_audit import verify as verify_primary_etp
from .pq_official_url_sha_acquire import batch as fetch_official_url_sha
from .pq_verified_market_report import exact_filestore_sha_receipts
from .pq_b2b_primary_capture import batch as fetch_b2b
from .pq_b2b_primary_audit import verify as verify_b2b
from .pq_research_coverage import build as build_coverage
from .pq_project_links import resolve as resolve_projects
from .pq_verified_market_report import run as build_market_snapshot, markdown as market_markdown
from .pq_quality_gate import audit as audit_quality


def run_cycle(*, leads: Path, source_roots: list[Path], archive_index: Path,
              runtime: Path, ontology: Path, dp_source: Path,
              max_cases: int = 8, network: bool = True, verified_reestr: Path | None = None,
              etp_queue: Path | None = None,
              contract_root: Path | None = None,
              contract_day_scan: Path | None = None,
              public223_source: Path | None = None,
              commission_facts: Path | None = None,
              primary_etp_source: Path | None = None,
              primary_etp_facts: Path | None = None,
              official_filestore_source: Path | None = None,
              b2b_source: Path | None = None,
              project_links: Path | None = None) -> dict:
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
                max_cases=80, max_archives=120)
            canonical = runtime / "public223-canonical"
            report["public223_canonical"] = canonicalize_public_223(
                staged=expanded, output=canonical, max_files=500)
            report["public223_direct"] = merge_direct(
                source_root=public223_source, canonical=canonical,
                max_cases=80, max_files=500)
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
    if official_filestore_source is not None:
        report["official_filestore_fetch"] = (
            fetch_official_url_sha(
                leads=leads, root=official_filestore_source,
                journal=runtime / "official-url-sha-attempts.json",
                max_cases=min(max_cases, 3))
            if network else {"status": "skipped_offline"})
        if official_filestore_source.is_dir():
            bound = exact_filestore_sha_receipts(official_filestore_source)
            report["official_filestore_evidence"] = {
                "cases": len(bound),
                "sha_verified_files": sum(x["verified_file_instances"] for x in bound),
            }
            report["official_filestore_dp"] = ingest(
                sources=official_filestore_source,
                output=runtime / "dp-official-url-sha.json",
                dp_source=dp_source, max_files=min(max_cases * 4, 120))
            report["review_queues"].append(seed(
                sources=official_filestore_source, ontology=ontology,
                queue_dir=queue, max_cases=max_cases))
    if primary_etp_source is not None:
        report["primary_etp_fetch"] = (
            fetch_primary_etp(
                leads=leads, source_root=primary_etp_source,
                journal=runtime / "primary-etp-attempts.json",
                max_cards=min(max_cases, 4))
            if network else {"status": "skipped_offline"})
        if primary_etp_facts is not None:
            etp_facts = verify_primary_etp(
                facts=primary_etp_facts, source_root=primary_etp_source)
            etp_facts_file = runtime / "verified-primary-etp-facts.json"
            etp_facts_file.write_text(
                json.dumps(etp_facts, ensure_ascii=False, indent=2),
                encoding="utf-8")
            report["primary_etp_evidence"] = {
                "original_cards_verified": etp_facts["original_etp_cases_verified"],
                "signed_contracts_verified": etp_facts["signed_contracts_verified"],
                "artifact": str(etp_facts_file),
            }
    if b2b_source is not None:
        report["primary_b2b_fetch"] = (
            fetch_b2b(
                leads=leads, root=b2b_source,
                journal=runtime / "primary-b2b-attempts.json",
                max_cards=min(max_cases, 4))
            if network else {"status": "skipped_offline"})
        if b2b_source.is_dir():
            b2b_evidence = verify_b2b(source_root=b2b_source)
            (runtime / "verified-primary-b2b-facts.json").write_text(
                json.dumps(b2b_evidence, ensure_ascii=False, indent=2),
                encoding="utf-8")
            report["primary_b2b_evidence"] = {
                "original_cards_verified": b2b_evidence["first_party_cards_verified"],
                "signed_contracts_verified": 0,
                "results_hidden_cases": sum(
                    bool(x["results_hidden_by_organizer"])
                    for x in b2b_evidence["source_records"]),
            }
    if project_links is not None:
        required = (
            public223_source, official_filestore_source,
            primary_etp_source, primary_etp_facts, b2b_source,
            contract_root, commission_facts)
        if any(p is None for p in required):
            raise ValueError("Spec Kit source audit requires existing full primary-source inputs")
        assert public223_source is not None
        assert official_filestore_source is not None
        assert primary_etp_source is not None
        assert primary_etp_facts is not None
        assert b2b_source is not None
        assert contract_root is not None
        assert commission_facts is not None
        coverage = build_coverage(
            leads=leads, public223=public223_source,
            filestore=official_filestore_source,
            etp_facts=primary_etp_facts, etp_originals=primary_etp_source,
            b2b_originals=b2b_source,
            b2b_journal=runtime / "primary-b2b-attempts.json",
            eis_journal=runtime / "source-attempts.json",
            public_journal=runtime / "public223-attempts.json",
            primary_etp_journal=runtime / "primary-etp-attempts.json")
        resolved = resolve_projects(leads=leads, links=project_links, queue=queue)
        market = build_market_snapshot(
            leads=leads, eis_originals=public223_source,
            commission_facts=commission_facts, review_queue=queue,
            etp_facts=primary_etp_facts, etp_originals=primary_etp_source,
            contract_root=contract_root, day_scan=contract_day_scan,
            official_filestore_root=official_filestore_source,
            b2b_originals=b2b_source)
        quality = audit_quality(
            coverage=coverage, projects=resolved, market=market,
            data_platform=report.get("public223_data_platform"))
        for filename, artifact in (
                ("coverage.json", coverage),
                ("project_register.json", resolved),
                ("verified-market-snapshot.json", market),
                ("quality_report.json", quality)):
            (runtime / filename).write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2),
                encoding="utf-8")
        (runtime / "report.md").write_text(market_markdown(market), encoding="utf-8")
        report["spec_kit_evidence_closure"] = {
            "source_consistency_passed": quality["source_arithmetic_consistency_passed"],
            "data_platform_extraction_complete": quality["data_platform_extraction_complete"],
            "data_platform_extraction_status": quality["data_platform_extraction_status"],
            "pending_data_platform_original_files": quality["data_platform_pending_source_files"],
            "full_market_acceptance_passed": quality["full_market_acceptance_passed"],
            "primary_procedure_ids": quality["unique_primary_source_procedures"],
            "remaining_candidate_rows_without_primary": quality["source_missing_candidate_rows"],
            "reviewed_project_links": resolved["source_verified_relation_edges"],
            "unverified_signed_contract_suppliers": quality["verified_signed_contract_suppliers"],
            "artifacts": ["coverage.json", "project_register.json",
                          "verified-market-snapshot.json", "quality_report.json", "report.md"],
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
    p.add_argument("--primary-etp-source", type=Path)
    p.add_argument("--primary-etp-facts", type=Path)
    p.add_argument("--official-filestore-source", type=Path)
    p.add_argument("--b2b-source", type=Path)
    p.add_argument("--project-links", type=Path)
    a = p.parse_args()
    result = run_cycle(leads=a.leads, source_roots=a.source_root,
                       archive_index=a.archive_index, runtime=a.runtime,
                       ontology=a.ontology, dp_source=a.dp_source,
                       max_cases=a.max_cases, network=not a.offline, verified_reestr=a.verified_reestr, etp_queue=a.etp_queue,
                       contract_root=a.contract_root, contract_day_scan=a.contract_day_scan,
                       public223_source=a.public223_source,
                       commission_facts=a.commission_facts,
                       primary_etp_source=a.primary_etp_source,
                       primary_etp_facts=a.primary_etp_facts,
                       official_filestore_source=a.official_filestore_source,
                       b2b_source=a.b2b_source, project_links=a.project_links)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
