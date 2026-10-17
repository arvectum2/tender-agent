"""APR-06 live adapter is read-only, operator-gated, bounded and resumable."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.acceptance import run_apr06_probes as probe
from src.modules.commercial_acceptance.acceptance import AcceptanceError


def case(law: str = "44fz") -> dict:
    return {"reg_number": "0372200172326000015" if law == "44fz" else "32616197376",
            "law": law, "verification": {"state": "candidate"}}


def test_candidate_dry_run_does_not_invoke_eis(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_public_probe", lambda reg: pytest.fail("network access"))
    assert probe.probe_one(case(), tmp_path, execute=False)["stage"] == "DRY_RUN_READONLY_PROBE"
    assert not list(tmp_path.rglob("*"))


def test_223fz_is_explicitly_unsupported_not_44fz_mislabeled(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_public_probe", lambda reg: pytest.fail("wrong law"))
    assert probe.probe_one(case("223fz"), tmp_path, execute=True)["stage"] == "UNSUPPORTED_223FZ_SOAP_ROUTING"


def test_local_44fz_run_records_human_gate_and_reuses_completed_checkpoint(tmp_path, monkeypatch):
    call_log = []

    def acquire(reg):
        call_log.append(("getdocs", reg))
        return {"run_id": "synthetic-eis-run", "downloaded_files_count": 3,
                "run_status": "ready_to_analyze", "eis_reference": reg,
                "external_action_allowed": False}

    def analyze(run):
        call_log.append(("analyze", run))
        return {"run_id": run, "analysis_status": "completed_with_warnings",
                "human_control_required": True, "external_action_allowed": False}

    monkeypatch.setattr(probe, "_public_probe", acquire)
    monkeypatch.setattr(probe, "_analyze_bound_run", analyze)
    first = probe.probe_one(case(), tmp_path, execute=True)
    assert first["stage"] == "HUMAN_REVIEW_PENDING"
    saved = json.loads((tmp_path / case()["reg_number"] / "source.json").read_text())
    assert saved["verified_eis_document_hashes"] is False
    assert saved["operator_decision"] is None
    next_result = probe.probe_one(case(), tmp_path, execute=True)
    assert next_result["stage"] == "REUSED_CHECKPOINT"
    assert call_log == [("getdocs", case()["reg_number"]), ("analyze", "synthetic-eis-run")]


def test_crash_after_readonly_acquisition_resumes_exact_same_run(tmp_path, monkeypatch):
    called = {"acquire": 0, "analyze": 0}

    def acquire(reg):
        called["acquire"] += 1
        return {"run_id": "saved-run", "downloaded_files_count": 1,
                "run_status": "ready_to_analyze", "eis_reference": reg,
                "external_action_allowed": False}

    def analyze(run):
        called["analyze"] += 1
        if called["analyze"] == 1:
            raise RuntimeError("transient local analysis crash")
        return {"run_id": run, "analysis_status": "completed_with_warnings",
                "external_action_allowed": False}

    monkeypatch.setattr(probe, "_public_probe", acquire)
    monkeypatch.setattr(probe, "_analyze_bound_run", analyze)
    assert probe.probe_one(case(), tmp_path, execute=True)["stage"] == "ANALYSIS_FAILED"
    assert probe.probe_one(case(), tmp_path, execute=True)["stage"] == "HUMAN_REVIEW_PENDING"
    assert called == {"acquire": 1, "analyze": 2}


def test_no_docs_fails_closed_and_leaves_no_case(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_public_probe", lambda reg: {
        "run_id": "r", "downloaded_files_count": 0,
        "external_action_allowed": False,
    })
    assert probe.probe_one(case(), tmp_path, execute=True)["stage"] == "INTAKE_FAILED"
    assert not list(tmp_path.rglob("source.json"))


def test_tampered_prior_checkpoint_is_rejected(tmp_path, monkeypatch):
    src = tmp_path / case()["reg_number"]
    src.mkdir()
    (src / "source.json").write_text(json.dumps({
        "reg_number": case()["reg_number"], "run_id": "r",
        "external_action_allowed": True,
    }))
    with pytest.raises(AcceptanceError, match="tampered"):
        probe.probe_one(case(), tmp_path, execute=True)


def test_bounded_driver_validates_candidates_without_calling_external_services(tmp_path, capsys):
    manifest = Path(__file__).resolve().parents[1] / "docs/acceptance/apr06_candidate_pool_2026-10-09.json"
    code = probe.main(["--manifest", str(manifest), "--output-dir", str(tmp_path),
                       "--max-cases", "2"])
    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["executed"] is False
    assert parsed["submitted_bids"] == 0
    assert parsed["human_reviews_collected"] == 0
    assert parsed["acceptance_completed"] is False
    assert not list(tmp_path.iterdir())


def test_driver_rejects_invalid_case_count(tmp_path, capsys):
    manifest = Path(__file__).resolve().parents[1] / "docs/acceptance/apr06_candidate_pool_2026-10-09.json"
    assert probe.main(["--manifest", str(manifest), "--output-dir", str(tmp_path),
                       "--max-cases", "100"]) == 2
    assert "max-cases" in capsys.readouterr().out
