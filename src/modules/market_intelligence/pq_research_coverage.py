"""Coverage ledger for real v29 Power Quality procurement candidates.

Separates evidence availability from market completeness. A 223-FZ search hit
is not an original protocol. An aggregator mention is not primary-platform
coverage. Monthly gaps are explicit until true month-bounded discovery has
been run and recorded by the source provider. No source content is committed.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .pq_b2b_primary_audit import verify as verify_b2b
from .pq_primary_etp_audit import verify as verify_etp
from .pq_verified_market_report import (
    exact_filestore_sha_receipts,
    source_receipts,
)


def _number_category(value: object) -> str:
    if isinstance(value, str) and re.fullmatch(r"\d{11}", value):
        return "223fz"
    if isinstance(value, str) and re.fullmatch(r"\d{19}", value):
        return "44fz_candidate_unverified"
    return "commercial_or_unresolved"


def _source_year(number: str) -> int | None:
    """Notice-year *hint* in 223 registry number, not the publication date."""
    if not re.fullmatch(r"3(2[0-9])\d{8}", number):
        return None
    value = 2000 + int(number[1:3])
    return value if 2020 <= value <= 2039 else None


def _journal(path: Path | None, schema: str) -> list[dict]:
    if path is None or not path.exists():
        return []
    if path.is_symlink():
        raise ValueError("Symlinked source attempt journal")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != schema:
        raise ValueError("Unexpected source attempt journal schema")
    items = data.get("attempts")
    if not isinstance(items, list) or len(items) > 20000:
        raise ValueError("Invalid bounded source attempt journal")
    return items


def _months(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if a > b or a.year < 2000 or b.year > 2050:
        raise ValueError("Invalid study window")
    months = []
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        months.append(f"{y:04d}-{m:02d}")
        if len(months) > 60:
            raise ValueError("Excessive period audit range")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def build(*, leads: Path, public223: Path, filestore: Path,
          etp_facts: Path, etp_originals: Path,
          b2b_originals: Path | None = None,
          b2b_journal: Path | None = None,
          eis_journal: Path | None = None,
          public_journal: Path | None = None,
          primary_etp_journal: Path | None = None,
          start: str = "2024-01-01", end: str = "2026-10-28") -> dict:
    data = json.loads(leads.read_text(encoding="utf-8"))
    if not isinstance(data.get("records"), list) or len(data["records"]) > 20000:
        raise ValueError("Missing or oversized candidate corpus")
    corpus = data["records"]
    eis = {r["registry_number"]: r for r in source_receipts(public223)}
    original_sha = {r["registry_number"]: r
                    for r in exact_filestore_sha_receipts(filestore)}
    verified_etp = verify_etp(facts=etp_facts, source_root=etp_originals)
    etp = {x["procedure_id"]: x for x in verified_etp["records"]}
    b2b = {x["procedure_id"]: x for x in verify_b2b(
        source_root=b2b_originals)["source_records"]} if b2b_originals is not None else {}
    found = _journal(eis_journal, "pq-source-attempts/1")
    downloads = _journal(public_journal, "pq-223-public-page-attempts/1")
    native = _journal(primary_etp_journal, "pq-etp-primary-attempts/1")
    b2b_attempts = _journal(b2b_journal, "pq-original-b2b-capture-attempts/1")
    found_ids = {str(r.get("procedure_id")) for r in found
                 if r.get("source") == "official_eis_search"
                 and r.get("status") == "success"
                 and r.get("matches")}
    attempted_download_ids = {str(r.get("registry_number")) for r in downloads}
    native_ids = {str(r.get("procedure_id")) for r in native}
    b2b_attempt_ids = {str(r.get("procedure_id")) for r in b2b_attempts}
    cases = []
    seen = set()
    source_hosts = Counter()
    yearly = defaultdict(lambda: {"223_candidate_lot_rows": 0,
                                  "distinct_223_notices": 0,
                                  "distinct_223_notices_with_files": 0})
    year_numbers = defaultdict(set)
    year_originals = defaultdict(set)
    unique_source_223_with_files = set()
    unique_native_etp = set()
    unique_b2b_etp = set()
    statuses = Counter()
    for row in corpus:
        canonical = row.get("canonical_id")
        if not isinstance(canonical, str) or not canonical or canonical in seen:
            raise ValueError("Missing or duplicate canonical candidate identity")
        seen.add(canonical)
        number = str(row.get("procedure_id") or "")
        kind = _number_category(number)
        source_tiers = sorted({
            str(e.get("source_tier", "")) for e in (row.get("evidence") or [])
            if isinstance(e, dict) and e.get("source_tier")
        })
        urls = [e.get("url") for e in (row.get("evidence") or [])
                if isinstance(e, dict) and isinstance(e.get("url"), str)]
        for url in urls:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme == "https" and parsed.hostname:
                source_hosts[parsed.hostname.lower()] += 1
        count = 0
        proof = []
        year = None
        if kind == "223fz":
            pub = eis.get(number)
            direct = original_sha.get(number)
            if pub is not None:
                count += pub["verified_file_instances"]
                proof.append("official_223_public_page_receipt")
            if direct is not None:
                count += direct["verified_file_instances"]
                proof.append("official_223_exact_url_sha_receipt")
            if count:
                state = "original_eis_documents_verified"
            elif pub is not None or direct is not None:
                state = "official_notice_receipt_without_files"
            elif number in found_ids:
                state = "official_search_hit_no_document_receipt"
            else:
                state = "primary_source_not_verified"
            year = _source_year(number)
            year_key = str(year) if year is not None else "unknown"
            yearly[year_key]["223_candidate_lot_rows"] += 1
            year_numbers[year_key].add(number)
            if count:
                year_originals[year_key].add(number)
                unique_source_223_with_files.add(number)
        elif number in etp:
            state = "original_commercial_card_html_sha_verified"
            proof.append("primary_bidzaar_html_sha_receipt")
            unique_native_etp.add(number)
        elif number in b2b:
            state = "original_commercial_b2b_html_sha_verified"
            proof.append("primary_b2b_html_sha_receipt")
            unique_b2b_etp.add(number)
        else:
            state = "secondary_or_unverified_source_only"
        statuses[state] += 1
        cases.append({
            "canonical_id": canonical,
            "procedure_id": number or None,
            "source_category": kind,
            "family": str(row.get("family") or ""),
            "scope_hypothesis": str(row.get("scope") or ""),
            "notice_year_hint_not_publication_date": year,
            "primary_source_state": state,
            "primary_source_proofs": proof,
            "original_eis_file_instances": count,
            "eis_exact_search_hit_recorded": number in found_ids,
            "public_notice_download_attempt_recorded": number in attempted_download_ids,
            "etp_original_card_attempt_recorded": number in native_ids,
            "b2b_original_card_attempt_recorded": number in b2b_attempt_ids,
            "candidate_source_tiers_not_validation": source_tiers,
            "publication_month_source_verified": None,
            "signed_contract_supplier_verified": False,
        })
    for year_key in yearly:
        yearly[year_key]["distinct_223_notices"] = len(year_numbers[year_key])
        yearly[year_key]["distinct_223_notices_with_files"] = len(year_originals[year_key])
    observed = len(corpus)
    by_kind = Counter(c["source_category"] for c in cases)
    all_223_numbers = {c["procedure_id"] for c in cases if c["source_category"] == "223fz"}
    numbered_223_rows = by_kind["223fz"]
    confirmed_primary = sum(c["primary_source_state"] in (
        "original_eis_documents_verified",
        "original_commercial_card_html_sha_verified",
        "original_commercial_b2b_html_sha_verified") for c in cases)
    periods = [
        {"month": m,
         "source_queries_with_verified_month_bounds": 0,
         "coverage_state": "not_demonstrated",
         "zero_procurements_claimed": False}
        for m in _months(start, end)
    ]
    return {
        "schema_version": "pq-discovery-coverage/1",
        "scope": "historical_v29_candidates_only_not_national_market",
        "study_start": start,
        "study_end": end,
        "candidate_denominator": observed,
        "source_category_counts": dict(sorted(by_kind.items())),
        "numbered_223_candidate_lot_rows": numbered_223_rows,
        "distinct_223_notice_numbers": len(all_223_numbers),
        "additional_lot_rows_sharing_223_notice": numbered_223_rows - len(all_223_numbers),
        "commercial_or_nonstandard_candidate_rows": by_kind["commercial_or_unresolved"] + by_kind["44fz_candidate_unverified"],
        "source_state_counts": dict(sorted(statuses.items())),
        "candidate_rows_with_primary_original": confirmed_primary,
        "candidate_rows_without_verified_primary_original": observed - confirmed_primary,
        "unique_notice_or_etp_numbers_with_primary_original": len(unique_source_223_with_files) + len(unique_native_etp) + len(unique_b2b_etp),
        "primary_original_source_types": {
            "official_223_unique_notices_with_files": len(unique_source_223_with_files),
            "original_commercial_etp_unique_cards": len(unique_native_etp),
            "original_b2b_center_unique_cards": len(unique_b2b_etp),
        },
        "source_223_year_hint_not_publication_date": dict(sorted(yearly.items())),
        "period_search_coverage": periods,
        "indexed_host_mentions_not_primary_source_coverage": dict(source_hosts.most_common()),
        "search_attempt_log": {
            "official_223_exact_number_queries": len(found),
            "public_223_download_attempts": len(downloads),
            "original_commercial_etp_capture_attempts": len(native),
            "original_b2b_center_capture_attempts": len(b2b_attempts),
        },
        "completeness": "partial_period_discovery_not_established",
        "cases": cases,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--public223", type=Path, required=True)
    p.add_argument("--filestore", type=Path, required=True)
    p.add_argument("--etp-facts", type=Path, required=True)
    p.add_argument("--etp-originals", type=Path, required=True)
    p.add_argument("--b2b-originals", type=Path)
    p.add_argument("--b2b-journal", type=Path)
    p.add_argument("--eis-journal", type=Path)
    p.add_argument("--public-journal", type=Path)
    p.add_argument("--etp-journal", type=Path)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2026-10-28")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = build(leads=a.leads, public223=a.public223, filestore=a.filestore,
                   etp_facts=a.etp_facts, etp_originals=a.etp_originals,
                   b2b_originals=a.b2b_originals, b2b_journal=a.b2b_journal,
                   eis_journal=a.eis_journal,
                   public_journal=a.public_journal,
                   primary_etp_journal=a.etp_journal,
                   start=a.start, end=a.end)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({
        key: value for key, value in result.items()
        if key not in ("cases", "period_search_coverage",
                       "indexed_host_mentions_not_primary_source_coverage",
                       "source_223_year_hint_not_publication_date")},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
