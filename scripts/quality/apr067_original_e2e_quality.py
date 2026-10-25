"""Revalidate one saved authentic-EIS development E2E from independent source bytes.

Never equate checked XML facts with all model claims or legal commercial gold.
No internet/LLM calls, no source mutation, no public output.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_TAGS = {"procurement_title": "purchaseObjectInfo", "application_deadline": "endDT", "nmck": "maxPrice"}
_RUN_ID = re.compile(r"toa-run-\d{14}-[a-f0-9]{6,16}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


class EvidenceError(ValueError):
    """Invalid record: no positive quality verdict."""


def _json(p: Path) -> dict:
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 5_000_000:
        raise EvidenceError("missing or unsafe JSON evidence")
    try:
        obj = json.loads(p.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("bad JSON evidence") from exc
    if not isinstance(obj, dict):
        raise EvidenceError("JSON evidence not an object")
    return obj


def _original(folder: Path, stored: object) -> bytes:
    if not isinstance(stored, str) or not stored or "\\" in stored:
        raise EvidenceError("unsafe original path")
    rel = Path(stored)
    root = folder.resolve()
    p = folder / rel
    if (rel.is_absolute() or ".." in rel.parts or not p.resolve().is_relative_to(root)
            or p.is_symlink() or not p.is_file() or p.stat().st_size > 100_000_000):
        raise EvidenceError("missing or unsafe original")
    return p.read_bytes()


def _xml_value(raw: bytes, tag: str) -> list[str]:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise EvidenceError("unsafe XML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise EvidenceError("invalid official XML") from exc
    return list(dict.fromkeys(
        (node.text or "").strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == tag and (node.text or "").strip()
    ))


def _ratio(num: int, den: int) -> dict:
    if not den or not 0 <= num <= den:
        raise EvidenceError("invalid metric denominator")
    return {"state": "OBSERVED_SOURCE_VERIFIED_SUBSET", "numerator": num,
            "denominator": den, "value": round(num / den, 6)}


def _unmeasured(reason: str) -> dict:
    return {"state": "NOT_MEASURED", "value": None, "reason": reason}


def inspect(*, root: Path, receipt: dict, run: dict, replay: dict, proof: dict) -> dict:
    run_id = receipt.get("run_id")
    number = receipt.get("notice_number")
    if (receipt.get("stage") != "development_e2e"
            or receipt.get("reviewer_kind") != "owner_delegated_chatgpt"
            or not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id)
            or not isinstance(number, str) or not re.fullmatch(r"\d{19}", number)
            or run.get("run_id") != run_id or run.get("procurement_id") != number
            or proof.get("run_id") != run_id or proof.get("registry_number") != number
            or proof.get("source_selection") != "single_registry_matched_xml"
            or run.get("procurement_source") != "zakupki_gov_ru_getdocs_ip"
            or receipt.get("current_official_revision_verified") is not False):
        raise EvidenceError("notice/run identity or revision mismatch")
    provenance = run.get("ai_runtime_provenance")
    if (run.get("analysis_mode") != "llm_tender_operator_provider"
            or not isinstance(provenance, dict)
            or provenance.get("llm_invoked") is not True
            or provenance.get("llm_provider") != "openai_compatible"
            or provenance.get("llm_endpoint_host") not in {"127.0.0.1", "localhost"}
            or provenance.get("fallback_reason") is not None
            or type(provenance.get("llm_calls_count")) is not int
            or provenance["llm_calls_count"] < 1
            or replay.get("analysis_http") != 200
            or replay.get("persisted_llm_invoked") is not True
            or replay.get("persisted_analysis_mode") != "llm_tender_operator_provider"):
        raise EvidenceError("actual model invocation not evidenced")
    latency = replay.get("analysis_elapsed_seconds")
    if type(latency) not in (float, int) or not math.isfinite(latency) or latency <= 0:
        raise EvidenceError("missing/invalid model-only duration")
    if (run.get("external_actions") is not False
            or any(run.get(k) is not True for k in ("no_digital_signature", "no_email_sending", "no_platform_submission"))
            or any(receipt.get(k) is not False for k in (
                "bid_submitted", "digital_signature_used", "payment_created",
                "production_mutated", "etp_mutated", "owner_legal_go_granted"))):
        raise EvidenceError("unsafe commercial/bid boundary")
    originals = receipt.get("official_originals")
    files = run.get("files")
    if not isinstance(originals, list) or not isinstance(files, list) or not files or len(originals) != len(files):
        raise EvidenceError("original file denominator missing")
    by_name = {}
    for row in originals:
        if not isinstance(row, dict) or not isinstance(row.get("original_name"), str) or row["original_name"] in by_name:
            raise EvidenceError("duplicate/missing official original")
        by_name[row["original_name"]] = row
    copied = root / "sources" / "input"
    saved = root / "qa-final-render" / "runs" / run_id
    by_id = {}
    digests = {}
    for row in files:
        if not isinstance(row, dict) or not isinstance(row.get("file_id"), str) or row["file_id"] in by_id:
            raise EvidenceError("duplicate/missing file id")
        name = row.get("display_name")
        claim = by_name.get(name)
        if (not isinstance(claim, dict) or claim.get("verified_from_official") is not True
                or not _SHA.fullmatch(str(claim.get("sha256")))
                or row.get("extracted_text_available") is not True
                or row.get("text_extraction_status") != "extracted"):
            raise EvidenceError("missing official source or extracted text")
        actual = _original(saved / "input", row.get("stored_name"))
        separate = _original(copied, row.get("stored_name"))
        digest = hashlib.sha256(actual).hexdigest()
        if digest != hashlib.sha256(separate).hexdigest() or digest != claim["sha256"]:
            raise EvidenceError("source bytes tampered, or SHA differs")
        by_id[row["file_id"]] = (row, actual)
        digests[row["file_id"]] = digest
    if replay.get("extracted_original_count") != len(files) or replay.get("failed_original_count") != 0:
        raise EvidenceError("extraction counters disagree")
    if (any(replay.get(k) != 200 for k in (
            "authenticated_workspace", "history_http", "reopen_http",
            "read_only_registry_http", "report_json_http", "source_evidence_http"))
            or any(replay.get(k) != 401 for k in (
                "unauth_workspace", "unauth_report", "unauth_evidence"))
            or any(replay.get(k) != 409 for k in ("pdf_export_http", "docx_export_http"))):
        raise EvidenceError("archival export, authenticated readback, or access boundary missing")
    event_file = saved / "events.jsonl"
    if event_file.is_symlink() or not event_file.is_file() or event_file.stat().st_size > 4_000_000:
        raise EvidenceError("missing independent original source event log")
    events = set()
    try:
        for line in event_file.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):
                raise EvidenceError("invalid source event")
            events.add(event.get("event_type"))
    except (UnicodeError, ValueError) as exc:
        raise EvidenceError("unreadable source event log") from exc
    if not {"eis_getdocs_started", "eis_archive_downloaded",
            "run_created_from_eis_archive", "llm_analysis_completed"} <= events:
        raise EvidenceError("missing source acquisition or model event")
    rp = saved / "output" / "report.html"
    if rp.is_symlink() or not rp.is_file() or rp.stat().st_size > 10_000_000:
        raise EvidenceError("missing saved rendered HTML")
    report = rp.read_bytes()
    report_sha = hashlib.sha256(report).hexdigest()
    if report_sha != receipt.get("report_sha256"):
        raise EvidenceError("report digest mismatch")
    try:
        report_html = report.decode("utf-8")
    except UnicodeError as exc:
        raise EvidenceError("invalid report encoding") from exc
    if report_html.count('id="official-eis-citations"') != 1:
        raise EvidenceError("missing or duplicated official XML citation section")
    panel = report_html.split('<section id="official-eis-citations">', 1)[1].split("</section>", 1)[0]
    facts = proof.get("facts")
    if not isinstance(facts, dict):
        raise EvidenceError("no source fact proof")
    citations = []
    for key, tag in _TAGS.items():
        fact = facts.get(key)
        if not isinstance(fact, dict) or fact.get("status") != "KNOWN":
            raise EvidenceError(f"selected fact missing: {key}")
        refs = fact.get("evidence")
        if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], dict):
            raise EvidenceError(f"ambiguous source: {key}")
        ref = refs[0]
        file_id = ref.get("file_id")
        if file_id not in by_id:
            raise EvidenceError("source ref does not bind to saved original")
        doc, raw = by_id[file_id]
        xml_notice_ids = [x for x in _xml_value(raw, "purchaseNumber") if re.fullmatch(r"\d{19}", x)]
        if doc.get("extension") != ".xml" or xml_notice_ids != [number]:
            raise EvidenceError("wrong official XML revision or tender")
        if (ref.get("source_ref") != f"eis-xml:{file_id}:{tag}"
                or ref.get("locator") != f"XML:{tag}"
                or ref.get("document") != doc.get("display_name")
                or not isinstance(ref.get("excerpt"), str)
                or _xml_value(raw, tag) != [ref["excerpt"]]):
            raise EvidenceError(f"excerpt disagrees with original XML: {key}")
        if not all(html.escape(ref[field], quote=True) in panel
                   for field in ("source_ref", "excerpt", "document")):
            raise EvidenceError(f"HTML omits original citation: {key}")
        citations.append({"fact": key, "source_ref": ref["source_ref"], "original_sha256": digests[file_id]})
    return {
        "schema_version": "apr067-e2e-verified-subset-v1",
        "status": "DEVELOPMENT_SOURCE_SUBSET_VERIFIED",
        "scope": "one archived real 44fz E2E, not current EIS or all narrative claims",
        "notice_number": number, "run_id": run_id, "case_count": 1,
        "reviewer_kind": "owner_delegated_chatgpt", "independent_human_gold": False,
        "model_invoked": True, "model_calls": provenance["llm_calls_count"],
        "analysis_function_seconds": round(float(latency), 2),
        "originals_sha256_by_file_id": digests,
        "verified_selected_citations": citations, "report_sha256": report_sha,
        "metrics": {
            "saved_source_sha_match": _ratio(len(digests), len(files)),
            "files_with_extracted_text_flag": _ratio(len(files), len(files)),
            "selected_original_XML_citation_integrity": _ratio(len(citations), len(_TAGS)),
            "all_material_model_claim_accuracy": _unmeasured("full model claim inventory and independent truth unavailable"),
            "human_gold_false_go": _unmeasured("no qualified independently labeled legal GO outcomes"),
            "human_correction_rate": _unmeasured("owner corrections after workflow stabilization"),
            "rolling_e2e_p95": _unmeasured("one analysis call is not an end-to-end SLO distribution"),
            "current_official_revision_coverage": _unmeasured("archival notice; latest edition not retrieved"),
            "missing_legal_blocker_rate": _unmeasured("no independently labeled legal blockers"),
        },
        "commercial_acceptance": "NOT_MEASURED", "model_promotion_authorized": False,
        "bid_or_payment_authorized": False,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--stage", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    opts = cli.parse_args()
    root = opts.stage.resolve()
    if root.name != "ta-apr03b-e2e-20261015":
        cli.error("restricted to designated verified private E2E stage")
    try:
        receipt = _json(root / "output" / "development_e2e_receipt.json")
        replay = _json(root / "output" / "isolated_real_llm_e2e_result.json")
        run_id = receipt.get("run_id")
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise EvidenceError("bad run id")
        saved = root / "qa-final-render" / "runs"
        run = _json(saved / run_id / "metadata.json")
        os.environ["AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR"] = str(saved)
        from src.modules.tender_operator_agent_demo.operator_workspace_evidence import (
            get_operator_source_evidence,
        )
        proof = get_operator_source_evidence(run_id)
        result = inspect(root=root, receipt=receipt, run=run, replay=replay, proof=proof)
        output = opts.output.resolve()
        if output.parent != (root / "output").resolve():
            raise EvidenceError("output outside private source evidence directory")
        with output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    except (EvidenceError, OSError, ValueError, KeyError) as exc:
        print(f"APR067_BLOCKED: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps({
        "status": result["status"], "case_count": 1,
        "originals": len(result["originals_sha256_by_file_id"]),
        "checked_citations": len(result["verified_selected_citations"]),
        "analysis_function_seconds": result["analysis_function_seconds"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
