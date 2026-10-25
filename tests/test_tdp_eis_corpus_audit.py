"""Structural acceptance inventory must not disclose documents or write back."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ops.audit_tdp_eis_corpus import audit_corpus


def _run(root: Path, run: str, number: str, *, with_original=True, report=False):
    folder = root / run
    (folder / "input").mkdir(parents=True)
    if with_original:
        (folder / "input" / "notice.xml").write_bytes(b"<xml>private-business-data</xml>")
    if report:
        (folder / "output").mkdir()
        (folder / "output" / "report.json").write_text(json.dumps({"sections": []}))
    metadata = {
        "procurement_id": number,
        "status": "needs_review",
        "customer_email": "secret@company.example",
        "files": [{
            "stored_name": "notice.xml",
            "extracted_text_available": True,
        }],
        "_verified_notice_facts": {"source_file_id": "FILE-01"},
        "ai_runtime_provenance": {"llm_invoked": False},
    }
    (folder / "metadata.json").write_text(json.dumps(metadata))
    return folder


def test_reports_unique_procurements_and_selects_best_existing_evidence(tmp_path):
    _run(tmp_path, "run-a", "0372200172326000015", with_original=False, report=False)
    _run(tmp_path, "run-b", "0372200172326000015", with_original=True, report=True)
    _run(tmp_path, "run-c", "32616450723", with_original=True, report=False)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    report = audit_corpus(tmp_path)
    after = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert report["unique_procurements"] == 2
    assert report["all_eis_runs"] == 3
    assert report["best_run_structurally_complete"] == 1
    assert report["best_run_with_report"] == 1
    assert [x["run_id"] for x in report["procurements"]] == ["run-b", "run-c"]
    as_json = json.dumps(report)
    assert "secret@company" not in as_json
    assert "private-business-data" not in as_json
    assert report["acceptance_quality_verified"] is False


def test_path_traversal_does_not_count_original_file(tmp_path):
    outside = tmp_path / "notice.xml"
    outside.write_bytes(b"fake")
    folder = _run(tmp_path, "run-a", "0372200172326000015", with_original=False)
    p = folder / "metadata.json"
    meta = json.loads(p.read_text())
    meta["files"][0]["stored_name"] = "../../notice.xml"
    p.write_text(json.dumps(meta))
    report = audit_corpus(tmp_path)
    assert report["best_run_originals_missing"] == 1
    assert report["procurements"][0]["original_files_present"] == 0


def test_malformed_numbers_are_excluded(tmp_path):
    _run(tmp_path, "run-a", "unknown")
    _run(tmp_path, "run-b", "123")
    report = audit_corpus(tmp_path)
    assert report["unique_procurements"] == 0
    assert report["all_eis_runs"] == 0
