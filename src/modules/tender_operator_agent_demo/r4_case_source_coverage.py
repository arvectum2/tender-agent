"""Conservative 20-case historical EIS source coverage for existing R4/R5 gold.

Consumes previously archived independent verification CSVs. It does NOT
fetch live EIS, inspect private binaries, confirm bidder eligibility, certify
human review, or decide GO. Inconsistent source receipts abort the matrix.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_REGISTRY = re.compile(r"\d{19}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CASE_PATTERN = re.compile(r"^\|\s*\d+\s*\|\s*(\d{19})\s*\|", re.MULTILINE)


def _rows(csv_text: str, *, source: str, unique_cases: bool = True) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or "reg_number" not in reader.fieldnames:
        raise ValueError(f"{source}: missing reg_number column")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError(f"{source}: duplicate column names")
    rows = list(reader)
    if any(None in row or not _REGISTRY.fullmatch(row.get("reg_number") or "") for row in rows):
        raise ValueError(f"{source}: malformed registry number or CSV shape")
    if unique_cases and len({r["reg_number"] for r in rows}) != len(rows):
        raise ValueError(f"{source}: duplicate registry entries")
    return rows


def _count(value: str, *, field: str) -> int:
    if not re.fullmatch(r"\d+", value or ""):
        raise ValueError(f"{field}: invalid nonnegative integer")
    return int(value)


def _sha(value: str, *, field: str) -> str:
    if not _SHA.fullmatch(value or ""):
        raise ValueError(f"{field}: invalid SHA256 receipt")
    return value


def _validate_consistency(case: dict[str, str], facts: dict[str, str]) -> None:
    if case["official_SOAP_status"] != facts["archive_status"]:
        raise ValueError("archive status differs between independent source matrices")
    if case["official_SOAP_status"] != "completed":
        if facts["deadline_match"] != "UNKNOWN" or facts["price_match"] != "UNKNOWN":
            raise ValueError("nonexistent official archive cannot prove typed facts")
        return
    if case["highest_archive_endDT"] != facts["archive_deadline"]:
        raise ValueError("archive deadline differs between source matrices")
    if case["highest_archive_max_price_RUB"] != facts["archive_max_price"]:
        # One source can format decimals differently, but never accept two
        # distinct numeric amounts.
        try:
            if Decimal(case["highest_archive_max_price_RUB"]) != Decimal(facts["archive_max_price"]):
                raise ValueError("archive price differs between source matrices")
        except InvalidOperation as exc:
            raise ValueError("archive price invalid") from exc
    for field, left, right, status in (
        ("deadline", facts["persisted_deadline"], facts["archive_deadline"], facts["deadline_match"]),
        ("price", facts["persisted_initial_price"], facts["archive_max_price"], facts["price_match"]),
    ):
        if left and right:
            if field == "deadline":
                try:
                    equal = datetime.fromisoformat(left.replace("Z", "+00:00")) == datetime.fromisoformat(
                        right.replace("Z", "+00:00")
                    )
                except ValueError as exc:
                    raise ValueError("invalid source date") from exc
            else:
                try:
                    equal = Decimal(left) == Decimal(right)
                except InvalidOperation as exc:
                    raise ValueError("invalid source monetary value") from exc
            if (status == "EXACT") != equal or status not in {"EXACT", "MISMATCH"}:
                raise ValueError(f"{field}: stored mismatch label contradicts source values")


def build_r4_20_case_source_coverage(
    protocol_markdown: str,
    independent_cases_csv: str,
    independent_files_csv: str,
    persisted_facts_csv: str,
    human_queue_csv: str,
) -> dict[str, Any]:
    """Create a machine-only, dated-archive source inventory for existing 20 R4 cases."""
    expected = _CASE_PATTERN.findall(protocol_markdown)
    if len(expected) != 20 or len(set(expected)) != 20:
        raise ValueError("R4 protocol does not contain exactly 20 unique case IDs")
    cases = _rows(independent_cases_csv, source="independent_cases")
    files = _rows(independent_files_csv, source="independent_files", unique_cases=False)
    persisted = _rows(persisted_facts_csv, source="persisted_facts")
    human = _rows(human_queue_csv, source="human_review_queue")
    keys = set(expected)
    for name, data in (("independent_cases", cases), ("persisted_facts", persisted),
                       ("human_review_queue", human)):
        if len(data) != 20 or {r["reg_number"] for r in data} != keys:
            raise ValueError(f"{name}: case IDs disagree with canonical R4 protocol")
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    file_keys: set[tuple[str, str]] = set()
    for f in files:
        reg, file_id = f["reg_number"], f["file_id"]
        if reg not in keys or not re.fullmatch(r"FILE-\d{2,}", file_id):
            raise ValueError("file receipt is not attributable to an R4 case")
        pair = (reg, file_id.casefold())
        if pair in file_keys:
            raise ValueError("duplicate file ID within a purchase")
        file_keys.add(pair)
        _sha(f["historic_SHA256"], field="historical file hash")
        _count(f["file_size_bytes"], field="original byte size")
        if f["cached_bytes_SHA_match"] != "YES":
            raise ValueError("historical original byte digest mismatch")
        if f["extension"] == ".xml":
            if f["official_XML_SHA_match"] != "YES":
                raise ValueError("unverified original XML cannot be official evidence")
        elif f["official_binary_retransfer_SHA_match"] not in {
            "NOT_CONFIRMED", "YES",
        }:
            raise ValueError("unknown official binary transfer status")
        by_file[reg].append(f)
    indexed_cases = {x["reg_number"]: x for x in cases}
    indexed_facts = {x["reg_number"]: x for x in persisted}
    indexed_human = {x["reg_number"]: x for x in human}
    result: list[dict[str, Any]] = []
    for registry in expected:
        case = indexed_cases[registry]
        fact = indexed_facts[registry]
        review = indexed_human[registry]
        _validate_consistency(case, fact)
        official = case["official_SOAP_status"] == "completed"
        if case["official_SOAP_status"] not in {"completed", "no_data"}:
            raise ValueError("unexpected official SOAP response state")
        attached = by_file[registry]
        n = len(attached)
        claimed = _count(case["historic_files_total"], field="historic file total")
        validated = _count(case["historic_files_SHA_verified"], field="verified historical count")
        if n != claimed or validated != n:
            raise ValueError("historical source file count disagrees with per-file receipts")
        if n != _count(review["file_count"], field="legacy count"):
            raise ValueError("historical count differs from human queue")
        if _count(review["hashed_file_count"], field="queue hashed count") != n:
            raise ValueError("queue hashed count differs from file source receipts")
        if official:
            _sha(case["official_zip_sha256"], field="official ZIP hash")
            if case["receipt_sha_matches_official_XML"] != "True" or n == 0:
                raise ValueError("completed archived source has no independently matched XML receipt")
        elif n or case["official_zip_sha256"]:
            raise ValueError("no_data cannot have trusted official archive or source receipts")

        originals = [f for f in attached if f["extension"] == ".xml"]
        binaries = [f for f in attached if f["extension"] != ".xml"]
        fresh_binary = sum(f["official_binary_retransfer_SHA_match"] == "YES" for f in binaries)
        xml_archive = _count(case["official_XML_bytes_matched"], field="official XML match")
        if official and xml_archive != len(originals):
            raise ValueError("official XML matched count not supported by source file receipts")
        if not official and xml_archive:
            raise ValueError("unavailable source has unexpectedly matched official XML")
        for attachment in binaries:
            if attachment["attachment_UID_in_official_XML"] != "YES":
                raise ValueError("binary attachment has no official XML UID cross-reference")

        stale = case["historical_notice_outdated"]
        if stale not in {"YES", "NO", "UNKNOWN"}:
            raise ValueError("unknown source edition status")
        if (not official) != (stale == "UNKNOWN"):
            raise ValueError("edition status contradicts official archive availability")
        if review["source_receipt_operator_reviewed"] != "false" or review["source_receipt_revision_human_verified"] != "false":
            # Never silently overwrite a later human action; this input
            # requires separate signed evidence review outside machine-only tool.
            raise ValueError("unexpected human review state needs independent audit")
        if any(review.get(k, "").strip() for k in (
            "human_go_no_go_defer", "human_reviewer", "human_review_timestamp",
            "human_signoff_reference",
        )):
            raise ValueError("human signoff exists and must be independently verified")
        if fact["human_signed"] != "NO" or case["human_verified"] != "NO":
            raise ValueError("human source verification cannot be inferred from machine CSVs")

        blockers = ["LIVE_EIS_STATUS_UNATTESTED", "HUMAN_R4_REVIEW_NOT_SIGNED",
                    "ARV001_RELEASE_NOT_APPROVED", "BIDDER_ELIGIBILITY_UNREVIEWED"]
        if not official:
            blockers.append("OFFICIAL_ARCHIVE_NO_DATA_NOT_NONEXISTENCE")
        if stale == "YES":
            blockers.append("RECEIPT_OUTDATED_VS_LATEST_ARCHIVED_NOTICE")
        if binaries and fresh_binary != len(binaries):
            blockers.append("OFFICIAL_ATTACHMENT_BINARY_RETRANSFER_NOT_CONFIRMED_IN_THIS_AUDIT")
        if fact["deadline_match"] == "MISMATCH":
            blockers.append("PERSISTED_REPORT_DEADLINE_CONTRADICTS_ARCHIVE")
        elif fact["deadline_match"] in {"PERSISTED_DEADLINE_MISSING", "UNKNOWN", "ARCHIVE_FIELD_UNAVAILABLE"}:
            blockers.append("PERSISTED_DEADLINE_NOT_VERIFIED")
        if fact["price_match"] == "MISMATCH":
            blockers.append("PERSISTED_REPORT_PRICE_CONTRADICTS_ARCHIVE")
        elif fact["price_match"] in {"PERSISTED_PRICE_MISSING", "UNKNOWN"}:
            blockers.append("PERSISTED_PRICE_NOT_VERIFIED")
        if case["stored_report_exists"] == "False":
            blockers.append("NO_HISTORICAL_REPORT")
        elif case["stored_report_exists"] != "True":
            raise ValueError("invalid historical report marker")
        receipt_status = "NO_OFFICIAL_ARCHIVE" if not official else (
            "STALE_NOTICE_RECEIPT" if stale == "YES" else
            "HISTORICAL_ORIGINAL_RECEIPTS_MATCHED"
        )
        result.append({
            "reg_number": registry,
            "official_archive_status": "HISTORIC_ARCHIVED_ZIP" if official else "NO_DATA",
            "source_receipt_status": receipt_status,
            "official_zip_sha256": case["official_zip_sha256"] if official else None,
            "source_case_file_count": n,
            "cached_source_files_sha_matched": n,
            "archived_original_xml_matched": xml_archive,
            "attached_non_xml_files": len(binaries),
            "independent_original_binary_transfers_verified": fresh_binary,
            "historic_receipt_edition": case["original_receipt_notice_version"] or None,
            "highest_observed_archived_edition": case["highest_official_archived_version"] or None,
            "archived_deadline": case["highest_archive_endDT"] or None,
            "archived_max_price_rub": case["highest_archive_max_price_RUB"] or None,
            "persisted_report_exists": case["stored_report_exists"] == "True",
            "persisted_deadline_check": fact["deadline_match"],
            "persisted_price_check": fact["price_match"],
            "human_source_review": "NOT_VERIFIED",
            "human_reviewer": None,
            "human_review_timestamp": None,
            "human_signature": None,
            "expert_gold": False,
            "latest_official_notice_attested": False,
            "arv001_release_ready": False,
            "bid_ready": False,
            "blockers": sorted(set(blockers)),
        })
    result = sorted(result, key=lambda x: x["reg_number"])
    all_source_sha = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "r4_source_coverage_v1",
        "scope": "ARCHIVED_SOURCE_AUDIT_ONLY_NOT_LIVE_EIS_OR_LEGAL_GOLD",
        "source": "existing_R4_R5_first_party_audits_2026-10-11_12",
        "cases": result,
        "source_matrix_sha256": all_source_sha,
        "summary": {
            "total_r4_cases": len(result),
            "archived_official_zip": sum(r["official_archive_status"] == "HISTORIC_ARCHIVED_ZIP" for r in result),
            "official_soap_no_data": sum(r["official_archive_status"] == "NO_DATA" for r in result),
            "stale_archived_notice_receipts": sum(r["source_receipt_status"] == "STALE_NOTICE_RECEIPT" for r in result),
            "historic_file_sha_matched": sum(r["cached_source_files_sha_matched"] for r in result),
            "official_original_xml_matched": sum(r["archived_original_xml_matched"] for r in result),
            "non_xml_attached_binary_count": sum(r["attached_non_xml_files"] for r in result),
            "independent_binary_retransfers_matched_in_this_audit": sum(r["independent_original_binary_transfers_verified"] for r in result),
            "saved_historical_reports": sum(r["persisted_report_exists"] for r in result),
            "persisted_deadline_archive_mismatches": sum(r["persisted_deadline_check"] == "MISMATCH" for r in result),
            "persisted_price_archive_mismatches": sum(r["persisted_price_check"] == "MISMATCH" for r in result),
            "human_gold_reviews_completed": 0,
            "live_eis_accepted": 0,
            "arv001_releases": 0,
        },
        "human_gold_attested": False,
        "bid_ready": False,
    }
