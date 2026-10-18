"""Fail-closed offline consistency audit of frozen 20-case DEVELOPMENT model receipts.

This checks the historical committed metrics and append-only source-only correction;
it does not reread private original EIS binaries, run an LLM, measure rolling SLO,
accept legal truth, or modify frozen benchmark material.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

_ROOT = Path(__file__).resolve().parents[2]
_PREFIX = "APR067_R4_TWENTY_DISTINCT_TRUE_GEMMA_E2E_"
_DIRECTORY = _ROOT / "docs" / "quality"
ORIGINAL_PATH = _DIRECTORY / (_PREFIX + "COHORT_2026-10-16.json")
CORRECTED_PATH = _DIRECTORY / (_PREFIX + "CORRECTED_COHORT_2026-10-16.json")
ORIGINAL_SHA = "8d3b22e7635413253f51d48610f87e14ae0c80abf6415df6c5dd9b81ffc8df51"
CORRECTED_SHA = "4242037c650db5be8ca860d2517d43ab9a0ad919a2d985a6fd9a4f149f8acaae"
_CORRECTED_NUMBER = "0349100009326000005"
_NUMBER = re.compile(r"\d{19}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_RUN = re.compile(r"toa-run-\d{14}-[a-f0-9]{6,16}\Z")


class CohortIntegrityError(ValueError):
    """A frozen-development evidence claim cannot be supported."""


def _no_duplicate_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CohortIntegrityError("duplicate JSON key in source evidence")
        result[key] = value
    return result


def _parse(data: bytes) -> dict:
    if not 0 < len(data) <= 300_000:
        raise CohortIntegrityError("source evidence outside byte limit")
    try:
        value = json.loads(data, object_pairs_hook=_no_duplicate_keys)
    except (ValueError, UnicodeError) as exc:
        raise CohortIntegrityError("malformed saved development evidence") from exc
    if not isinstance(value, dict):
        raise CohortIntegrityError("saved source evidence is not an object")
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _duration(value: object) -> Decimal:
    if type(value) not in (float, int):
        raise CohortIntegrityError("model-only duration missing or nonnumeric")
    try:
        v = Decimal(str(value))
    except InvalidOperation as exc:
        raise CohortIntegrityError("invalid latency") from exc
    if not v.is_finite() or v <= 0:
        raise CohortIntegrityError("model-only latency not positive and finite")
    return v


def _verify_ledger(snapshot: dict, *, expected_acceptances: int) -> tuple[list[dict], list[Decimal]]:
    rows = snapshot.get("cases")
    if not isinstance(rows, list) or len(rows) != 20:
        raise CohortIntegrityError("development case denominator is not twenty")
    ids = [r.get("registry_number") for r in rows if isinstance(r, dict)]
    if (len(ids) != 20 or len(set(ids)) != 20
            or any(not isinstance(n, str) or not _NUMBER.fullmatch(n) for n in ids)):
        raise CohortIntegrityError("duplicate or invalid development source identity")

    model_times = []
    accepted = 0
    for row in rows:
        if (type(row.get("original_file_sha_count")) is not int
                or row["original_file_sha_count"] < 1
                or type(row.get("gemma4_local_llm_calls")) is not int
                or row["gemma4_local_llm_calls"] != 4
                or type(row.get("original_eis_xml_critical_source_citations")) is not int
                or row["original_eis_xml_critical_source_citations"] != 3
                or type(row.get("development_semantic_report_accepted")) is not bool):
            raise CohortIntegrityError("original/model/critical-citation count not evidenced")
        model_times.append(_duration(row.get("model_only_seconds")))
        accepted += row["development_semantic_report_accepted"]

    totals = (
        ("actual_distinct_original_case_count", len(rows)),
        ("technical_original_source_model_e2e_count", len(rows)),
        ("actual_true_local_gemma_provider_calls", sum(x["gemma4_local_llm_calls"] for x in rows)),
        ("original_firstparty_sha_file_count", sum(x["original_file_sha_count"] for x in rows)),
        ("actual_original_eis_xml_critical_fact_citations", sum(
            x["original_eis_xml_critical_source_citations"] for x in rows)),
        ("development_semantically_accepted_report_count", expected_acceptances),
    )
    if (any(type(snapshot.get(key)) is not int or snapshot[key] != count for key, count in totals)
            or accepted != expected_acceptances
            or snapshot.get("per_case_critical_xml_fields") != [
                "procurement_title", "application_deadline", "nmck"
            ]):
        raise CohortIntegrityError("published summary disagrees with twenty individual runs")

    published = snapshot.get("local_model_analysis_only_seconds")
    ordered = sorted(model_times)
    expected = {
        "minimum": ordered[0],
        "median": Decimal(str(median(ordered))),
        "maximum": ordered[-1],
        "p90_nearest_rank": ordered[(9 * len(ordered) + 9) // 10 - 1],
        "total": sum(model_times),
    }
    if not isinstance(published, dict) or set(published) != set(expected):
        raise CohortIntegrityError("model-only latency summary incomplete")
    if any(_duration(published[k]) != v for k, v in expected.items()):
        raise CohortIntegrityError("reported duration statistics differ from twenty rows")
    if (not isinstance(snapshot.get("not_measured"), list)
            or any(not isinstance(s, str) for s in snapshot["not_measured"])
            or not any("time-to-decision" in s for s in snapshot["not_measured"])
            or not any("rolling production SLO" in s for s in snapshot["not_measured"])
            or not any("legal gold" in s for s in snapshot["not_measured"])):
        raise CohortIntegrityError("independent legal/production/time-to-decision caveats lost")
    return rows, model_times


def audit(original_bytes: bytes, corrected_bytes: bytes, *, check_pins: bool = True) -> dict:
    """Compare trusted original and corrected snapshots; never infer human gold."""
    old_sha, corrected_sha = _sha(original_bytes), _sha(corrected_bytes)
    if check_pins and (old_sha != ORIGINAL_SHA or corrected_sha != CORRECTED_SHA):
        raise CohortIntegrityError("published frozen cohort bytes changed")
    old, corrected = _parse(original_bytes), _parse(corrected_bytes)
    old_rows, _ = _verify_ledger(old, expected_acceptances=19)
    rows, durations = _verify_ledger(corrected, expected_acceptances=20)
    if (old.get("semantic_open_case") != [_CORRECTED_NUMBER]
            or corrected.get("semantic_open_case") != []
            or old.get("source_correction_provenance") is not None
            or corrected.get("not_measured") != old.get("not_measured")):
        raise CohortIntegrityError("source correction history or caveats tampered")
    for key in old.keys() | corrected.keys():
        if key not in {
            "cases", "development_semantically_accepted_report_count",
            "semantic_open_case", "semantic_open_case_explanation", "source_correction_provenance",
        } and old.get(key) != corrected.get(key):
            raise CohortIntegrityError("frozen model metrics changed during source-only correction")

    changes = []
    for before, after in zip(old_rows, rows, strict=True):
        if before["registry_number"] != after["registry_number"]:
            raise CohortIntegrityError("source order/identity replaced")
        if before == after:
            continue
        changes.append(before["registry_number"])
        for key in before.keys() | after.keys():
            if (key not in {"status", "development_semantic_report_accepted"}
                    and before.get(key) != after.get(key)):
                raise CohortIntegrityError("historical model inputs/metrics were rewritten")
        if (before["registry_number"] != _CORRECTED_NUMBER
                or before["development_semantic_report_accepted"] is not False
                or after["development_semantic_report_accepted"] is not True
                or before.get("status") != "source_model_passed_old_report_semantic_defect_not_closed"
                or after.get("status") != "development_source_only_appendonly_report_corrected_real_Gemma_original_unchanged"):
            raise CohortIntegrityError("unauthorized semantic acceptance rewrite")
    if changes != [_CORRECTED_NUMBER]:
        raise CohortIntegrityError("expected exactly one documented source-only correction")

    proof = corrected.get("source_correction_provenance")
    if not isinstance(proof, dict):
        raise CohortIntegrityError("corrected report original source provenance missing")
    expected_correction = next(r for r in rows if r["registry_number"] == _CORRECTED_NUMBER)
    if (proof.get("registry_number") != _CORRECTED_NUMBER
            or not isinstance(proof.get("run_id"), str)
            or not _RUN.fullmatch(proof["run_id"])
            or proof.get("original_prior_19_20_cohort_sha256") != old_sha
            or type(proof.get("new_model_calls")) is not int
            or proof["new_model_calls"] != 0
            or type(proof.get("source_original_sha_files")) is not int
            or proof["source_original_sha_files"] != expected_correction["original_file_sha_count"]
            or proof.get("source_eis_xml_citations") != 3
            or proof.get("revision") != "source-correction-v1"):
        raise CohortIntegrityError("append-only source correction provenance unbound")
    hash_fields = ("original_report_json_sha256", "original_report_html_sha256",
                   "corrected_report_json_sha256", "corrected_report_html_sha256")
    if any(not isinstance(proof.get(k), str) or not _SHA.fullmatch(proof[k]) for k in hash_fields):
        raise CohortIntegrityError("corrected report hash provenance incomplete")
    if any(proof[f"original_report_{fmt}_sha256"] == proof[f"corrected_report_{fmt}_sha256"]
           for fmt in ("json", "html")):
        raise CohortIntegrityError("correction reused original defective report hash")
    return {
        "contract_version": "apr067_corrected_20_development_consistency_v1",
        "state": "CHECKED_SAVED_DEV_METADATA_NOT_CURRENT_EIS",
        "original_snapshot_sha256": old_sha,
        "corrected_snapshot_sha256": corrected_sha,
        "distinct_archived_original_case_ids": len(rows),
        "model_provider_calls_recorded": sum(r["gemma4_local_llm_calls"] for r in rows),
        "original_file_sha_records": sum(r["original_file_sha_count"] for r in rows),
        "critical_eis_xml_citation_records": sum(
            r["original_eis_xml_critical_source_citations"] for r in rows),
        "source_only_semantic_corrections": changes,
        "new_llm_calls_for_source_correction": 0,
        "model_only_seconds": {
            "minimum": float(min(durations)),
            "median": float(median(durations)),
            "p90_nearest_rank": float(sorted(durations)[(9 * len(durations) + 9) // 10 - 1]),
            "maximum": float(max(durations)),
        },
        "true_operator_time_to_decision": None,
        "rolling_production_slo": None,
        "independent_legal_human_gold": None,
        "current_official_eis_revision_verified": False,
        "commercial_bid_go": False,
        "model_promotion_authorized": False,
    }


def main() -> int:
    try:
        for p in (ORIGINAL_PATH, CORRECTED_PATH):
            if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= 300_000:
                raise CohortIntegrityError("unsafe tracked source snapshot")
        result = audit(ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes())
    except (CohortIntegrityError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
