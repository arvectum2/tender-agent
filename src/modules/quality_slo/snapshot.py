"""APR-07 bounded quality/SLO evidence; read-only and not human acceptance."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from src.modules.benchmark_pipeline.contract import canonical_sha256


class QualityEvidenceError(ValueError):
    """Invalid evidence cannot claim SLO success."""

DP_FILES = ("embedding-0.6b.json", "embedding-4b.json", "embedding-8b.json",
            "reranker-qwen3-0.6b-vs-bge.json", "ocr-qwen3vl4b-vs-tesseract.json",
            "reasoning-qwen35-4b.json", "reasoning-qwen35-9b.json")

def load(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4_000_000:
        raise QualityEvidenceError(f"unsafe or missing evidence: {path.name}")
    blob = path.read_bytes()
    try:
        item = json.loads(blob)
    except (ValueError, UnicodeError) as exc:
        raise QualityEvidenceError(f"invalid evidence JSON: {path.name}") from exc
    if not isinstance(item, dict):
        raise QualityEvidenceError(f"non-object JSON: {path.name}")
    return item, hashlib.sha256(blob).hexdigest()

def unique(rows: object, key: str) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise QualityEvidenceError(f"missing source cases: {key}")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or row[key] in result:
            raise QualityEvidenceError(f"invalid or duplicate identifier: {key}")
        result[row[key]] = row
    return result

def ratio(n: int | None, d: int | None, basis: str) -> dict:
    if d in (None, 0):
        if n not in (None, 0):
            raise QualityEvidenceError(f"unknown denominator: {basis}")
        return {"value": None, "numerator": n, "denominator": d,
                "state": "NOT_MEASURED", "basis": basis}
    if type(n) is not int or type(d) is not int or not 0 <= n <= d:
        raise QualityEvidenceError(f"invalid metric counts: {basis}")
    return {"value": round(n / d, 6), "numerator": n, "denominator": d,
            "state": "OBSERVED_UNREVIEWED", "basis": basis}

def product_metrics(source: dict, machine: dict, audit: dict) -> dict:
    if (source.get("schema_version"), machine.get("schema_version"),
            audit.get("schema_version")) != (
        "apr06-readonly-receipts-v1", "apr06-machine-prefill-v1",
        "apr06-independent-gpt6-audit-v1"
    ):
        raise QualityEvidenceError("wrong provenance schema")
    if audit.get("human_operator_review") is not False or audit.get("human_signed_decisions") != 0:
        raise QualityEvidenceError("AI review falsely represented as HUMAN")
    cases = unique(source.get("cases"), "reg_number")
    reports = unique(machine.get("cases"), "notice")
    ai = unique(audit.get("cases"), "reg_number")
    if set(reports) != set(ai) or not set(reports).issubset(cases):
        raise QualityEvidenceError("review case set not bound to source")
    with_documents = total_files = parsed = text_flags = cited = unknowns = 0
    for reg, case in cases.items():
        files = case.get("document_files")
        if not isinstance(files, list) or case.get("status") not in {"completed_with_warnings", "needs_review", "completed", "docs_required"}:
            raise QualityEvidenceError(f"invalid acquisition record: {reg}")
        if len({f.get("file_id") for f in files if isinstance(f, dict)}) != len(files):
            raise QualityEvidenceError(f"duplicate document id: {reg}")
        for f in files:
            if (not isinstance(f, dict) or type(f.get("bytes")) is not int or f["bytes"] < 1
                    or not isinstance(f.get("sha256"), str) or len(f["sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in f["sha256"])):
                raise QualityEvidenceError(f"bad source checksum: {reg}")
        if (case["status"] != "docs_required") != (reg in reports):
            raise QualityEvidenceError(f"ready/report inconsistency: {reg}")
        total_files += len(files)
        with_documents += bool(files)
    for reg, item in reports.items():
        if item.get("human_reviewed") is not False:
            raise QualityEvidenceError("machine observations claimed human status")
        if item.get("run_id") != cases[reg].get("run_id") or item["run_id"] != ai[reg].get("run_id"):
            raise QualityEvidenceError(f"run id mismatch: {reg}")
        n, t = item.get("source_files"), item.get("source_text_available")
        if type(n) is not int or type(t) is not int or n != len(cases[reg]["document_files"]) or not 0 <= t <= n:
            raise QualityEvidenceError(f"invalid extracted denominator: {reg}")
        if type(item.get("decision_evidence_refs")) is not int or item["decision_evidence_refs"] < 0:
            raise QualityEvidenceError(f"invalid citation count: {reg}")
        if type(item.get("unknowns_count")) is not int or item["unknowns_count"] < 0:
            raise QualityEvidenceError(f"invalid unknown count: {reg}")
        parsed += n
        text_flags += t
        cited += bool(item["decision_evidence_refs"])
        unknowns += item["unknowns_count"]
    not_measured = ratio(None, None, "no_human_or_page_level_truth")
    return {
        "scope": "APR06_historical_44fz_intake_not_live_production",
        "cases": len(cases), "source_files": total_files, "analyzed_runs": len(reports),
        "machine_run_ids": sorted(row["run_id"] for row in reports.values()),
        "machine_unknown_flags": unknowns,
        "gpt6_flagged_stale_notice_cases": len(audit.get("critical_mismatches", [])),
        "attributed_human_reviews": 0,
        "metrics": {
            "document_acquisition_any_file": ratio(with_documents, len(cases), "44fz_intakes"),
            "analyzable_intakes": ratio(len(reports), len(cases), "44fz_intakes"),
            "machine_report_generated": ratio(len(reports), len(reports), "ready_runs"),
            "file_text_available_flag": ratio(text_flags, parsed, "machine_file_metadata"),
            "machine_decision_citation_presence": ratio(cited, len(reports), "machine_reports"),
            "human_verified_citation_accuracy": not_measured,
            "human_override_rate": not_measured,
            "ocr_fallback_rate": not_measured,
            "p95_analysis_latency": not_measured,
            "unsupported_document_rate": not_measured,
            "validated_unknown_rate": not_measured,
        },
    }

def bounded(value: object, label: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not math.isfinite(value) or not 0 <= value <= 1):
        raise QualityEvidenceError(f"invalid score: {label}")
    return round(float(value), 6)

def data_platform_evidence(path: Path) -> dict:
    """Import existing scoring JSON, not weights or inference services."""
    if path.is_symlink() or not path.is_dir():
        raise QualityEvidenceError("Data Platform result directory unavailable")
    payloads = {name: load(path / name) for name in DP_FILES}
    suites = {payloads[name][0].get("suite_sha256") for name in DP_FILES[:3]}
    corpora = {payloads[name][0].get("site_corpus_hash") for name in DP_FILES[:3]}
    if len(suites) != 1 or None in suites or len(corpora) != 1 or None in corpora:
        raise QualityEvidenceError("embedding candidates have incomparable suites")
    embeddings = {}
    for name in DP_FILES[:3]:
        item = payloads[name][0]
        if (type(item.get("docs")) is not int or item["docs"] < 1
                or type(item.get("queries")) is not int or item["queries"] < 1):
            raise QualityEvidenceError("missing embedding denominators")
        embeddings[name] = {
            "model": str(item.get("model", ""))[:128],
            "documents": item["docs"], "queries": item["queries"],
            "top1": bounded(item.get("top1"), f"{name}:top1"),
            "mrr": bounded(item.get("mrr"), f"{name}:mrr"),
            "ndcg_at5": bounded(item.get("ndcg_at5"), f"{name}:ndcg"),
            "recall_at5": bounded(item.get("recall_at5"), f"{name}:recall"),
        }
    ocr = payloads["ocr-qwen3vl4b-vs-tesseract.json"][0].get("summary")
    if not isinstance(ocr, dict) or not {"tesseract", "qwen3vl"} <= ocr.keys():
        raise QualityEvidenceError("incomplete OCR truth summary")
    ocr_scores = {}
    for label in ("tesseract", "qwen3vl"):
        row = ocr[label]
        if type(row.get("cases")) is not int or row["cases"] < 1:
            raise QualityEvidenceError("no OCR evaluated cases")
        ocr_scores[label] = {
            "cases": row["cases"], "mean_cer": bounded(row.get("mean_cer"), label),
            "mean_wer": bounded(row.get("mean_wer"), label),
        }
    reason = {}
    for name in DP_FILES[-2:]:
        item = payloads[name][0]; summary = item.get("summary")
        if not isinstance(summary, dict) or type(summary.get("cases")) is not int or summary["cases"] < 1:
            raise QualityEvidenceError("no grounded answer cases")
        reason[name] = {
            "model": str(item.get("model", ""))[:128], "cases": summary["cases"],
            "lexical_smoke_pass_rate": bounded(summary.get("combined_pass_rate"), name),
        }
    if payloads[DP_FILES[-1]][0].get("suite_sha256") != payloads[DP_FILES[-2]][0].get("suite_sha256"):
        raise QualityEvidenceError("reasoning models use different benchmark suites")
    return {
        "status": "EXPLORATORY_SITE_BENCHMARK_NOT_PROCUREMENT_GOLD",
        "source_result_sha256": {name: row[1] for name, row in payloads.items()},
        "embedding_scope": "45 Arvectum website pages; 12 Search Console queries, not procurement documents",
        "embeddings": embeddings, "ocr": ocr_scores, "reasoning": reason,
        "reranker_results_sha256": payloads["reranker-qwen3-0.6b-vs-bge.json"][1],
        "model_promotion": "BLOCKED_PENDING_FROZEN_PROCUREMENT_GOLD",
        "downloads_performed_by_tender_agent": False,
    }

def build_snapshot(repo_root: Path, dp_result_dir: Path | None = None) -> dict:
    base = repo_root / "docs" / "acceptance"
    names = (
        "apr06_real_probe_receipts_2026-10-09.json",
        "apr06_machine_prefill_2026-10-09.json",
        "apr06_independent_gpt6_audit_2026-10-09.json",
    )
    sources = [load(base / name) for name in names]
    result = {
        "schema_version": "apr07-quality-snapshot-v1",
        "snapshot_type": "bounded_historical_sample_NOT_production_SLO",
        "human_quality_approved": False, "commercial_acceptance_approved": False,
        "models_promoted": False, "models_downloaded": False,
        "sources_sha256": {name: obj[1] for name, obj in zip(names, sources, strict=True)},
        "procurement": product_metrics(*(x[0] for x in sources)),
        "data_platform": data_platform_evidence(dp_result_dir) if dp_result_dir else {
            "status": "NOT_MEASURED_NO_DP_REPORT"},
        "external_actions_performed": False,
    }
    result["snapshot_sha256"] = canonical_sha256(result)
    return result


def include_bounded_analysis_latency(snapshot: dict, logfile: Path) -> dict:
    """Measured historical run execution only; never claim end-to-end SLO."""
    if logfile.is_symlink() or not logfile.is_file() or logfile.stat().st_size > 1_000_000:
        raise QualityEvidenceError("missing or unsafe analysis log")
    blob = logfile.read_bytes()
    rows = []
    for line in blob.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except (UnicodeError, ValueError) as exc:
            raise QualityEvidenceError("invalid JSONL timing log") from exc
        if not isinstance(item, dict):
            raise QualityEvidenceError("invalid timing record")
        rows.append(item)
    if not rows:
        raise QualityEvidenceError("missing real analysis timings")
    seen = set()
    durations = []
    for item in rows:
        rid = item.get("run_id")
        seconds = item.get("elapsed_seconds")
        if not isinstance(rid, str) or rid in seen:
            raise QualityEvidenceError("duplicate or invalid run timing id")
        if (not isinstance(seconds, (int, float)) or isinstance(seconds, bool)
                or not math.isfinite(seconds) or seconds <= 0):
            raise QualityEvidenceError("invalid elapsed timing")
        if item.get("human_review_completed") is not False or item.get("external_actions") is not False:
            raise QualityEvidenceError("timing rows include consequential/human action")
        seen.add(rid)
        durations.append(float(seconds))
    # Source case roster preserved in AI audit, allowing strict ID binding.
    if seen != set(snapshot["procurement"]["machine_run_ids"]):
        raise QualityEvidenceError("timing source run IDs mismatch machine reports")
    # No extrapolation from a small sample; nearest-rank P95.
    durations.sort()
    result = dict(snapshot)
    result["latency_observation"] = {
        "state": "OBSERVED_UNREVIEWED",
        "scope": "local_analysis_function_call_only_not_ingest_to_human_decision",
        "run_count": len(rows), "p95_seconds_nearest_rank": durations[
            math.ceil(0.95 * len(durations)) - 1],
        "p50_seconds_nearest_rank": durations[
            math.ceil(0.50 * len(durations)) - 1],
        "maximum_seconds": max(durations),
        "log_sha256": hashlib.sha256(blob).hexdigest(),
    }
    result.pop("snapshot_sha256")
    result["snapshot_sha256"] = canonical_sha256(result)
    return result
