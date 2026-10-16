"""Read-only corpus audit: source SHA, provenance, split and run linkage checks."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.procurement_llm import audit_corpus


def make_row(
    oid: str,
    kind: str,
    ref: str,
    payload: dict,
    *,
    review: str = "source_documented",
    participation: str = "unknown",
    split: str = "development_exposed",
    status: str = "candidate_unreviewed",
) -> dict:
    return {
        "observation_id": oid,
        "event_kind": kind,
        "procurement_ref": ref,
        "review_state": review,
        "participation": participation,
        "candidate_split": split,
        "training_status": status,
        "payload_json": payload,
    }


def test_classifies_originals_without_promoting_chat_to_legal_gold(tmp_path):
    eis = tmp_path / "eis"
    reg = "0372200172326000015"
    folder = eis / reg
    folder.mkdir(parents=True)
    (folder / "tz.docx").write_bytes(b"fictional non-secret fixture")
    rows = [
        make_row(
            "a", "manual_review", reg,
            {"event_id": "review-001", "participation_evidence": "owner_chat_report"},
            review="owner_reported", participation="submitted", split="manual_candidate_not_blind",
        ),
    ]
    summary = audit_corpus.audit_observations(rows, set(), eis_root=eis)
    assert summary["total_observations"] == 1
    assert summary["manual_review_confidence"] == {"owner_reported": 1}
    assert summary["manual_participation"] == {"submitted": 1}
    assert summary["checks"]["existing_eis_originals"] == 1
    assert summary["checks"]["manual_no_sha_bound_receipt"] == 1
    assert summary["train_ready"] == summary["gold_claims_present"] == 0
    assert reg not in json.dumps(summary)


def test_dev_manifests_sha_verified_but_archive_not_proven(tmp_path):
    manifest = tmp_path / "source.json"
    metrics = tmp_path / "metrics.json"
    manifest.write_text('{"source":"fixture"}')
    metrics.write_text('{"metrics":"fixture"}')
    row = make_row("b", "development_e2e", "0000000000000000001", {
        "source_manifest_path": str(manifest),
        "source_manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
        "metrics_manifest_path": str(metrics),
        "metrics_manifest_sha256": sha256(metrics.read_bytes()).hexdigest(),
        "source": {"archived_zip_sha256": "a" * 64},
    })
    result = audit_corpus.audit_observations([row], set(), eis_root=tmp_path / "eis")
    assert result["checks"]["source_manifest_sha_verified"] == 1
    assert result["checks"]["metrics_manifest_sha_verified"] == 1
    assert result["checks"]["dev_archive_sha_recorded_not_file_verified"] == 1
    assert result["checks"]["no_eis_originals_locally"] == 1


def test_detects_deleted_manifests_missing_runs_and_duplicate_identity(tmp_path):
    rows = [
        make_row("dupe", "analysis_run", "manual:test", {"run_id": "missing", "report_path": "/not/available"}),
        make_row("dupe", "development_e2e", "0123456789012345678", {
            "source_manifest_path": str(tmp_path / "gone"),
            "source_manifest_sha256": "a" * 64,
            "metrics_manifest_path": str(tmp_path / "gone-metrics"),
            "metrics_manifest_sha256": "b" * 64,
        }),
    ]
    result = audit_corpus.audit_observations(rows, {"a valid run"}, eis_root=tmp_path)
    checks = result["checks"]
    assert result["unique_observations"] == 1
    assert checks["duplicate_observation_id"] == 1
    assert checks["missing_saved_analysis_run"] == 1
    assert checks["saved_report_path_missing"] == 1
    assert checks["source_manifest_missing_or_sha_mismatch"] == 1
    assert checks["metrics_manifest_missing_or_sha_mismatch"] == 1


def test_actual_sha_receipt_and_mismatch(tmp_path):
    p = tmp_path / "original.json"
    p.write_text('{"ok":true}', encoding="utf-8")
    good = make_row(
        "c", "manual_review", "0158300034526000388",
        {"event_id": "case-001", "primary_artifact": {
            "local_path": str(p), "sha256": sha256(p.read_bytes()).hexdigest()
        }},
        participation="submitted",
    )
    bad = make_row(
        "d", "manual_review", "0158300034526000388",
        {"event_id": "case-002", "primary_artifact": {
            "local_path": str(p), "sha256": "b" * 64
        }},
        participation="submitted",
    )
    result = audit_corpus.audit_observations([good, bad], set(), eis_root=tmp_path)
    assert result["checks"]["manual_original_sha_verified"] == 1
    assert result["checks"]["manual_original_missing_or_sha_mismatch"] == 1


def test_blind_gold_secrets_are_diagnosed_not_promoted(tmp_path):
    row = make_row("e", "manual_review", "sensitive", {
        "event_id": "review-001", "legal_gold": True, "raw_chat": "never expose this secret"
    }, split="blind_holdout", status="train_ready")
    result = audit_corpus.audit_observations([row], set(), eis_root=tmp_path)
    assert result["checks"]["protected_split_present"] == 1
    assert result["checks"]["unexpected_training_status"] == 1
    assert result["checks"]["sensitive_metadata_present"] == 1
    assert result["checks"]["unapproved_gold_claim_present"] == 1
    assert result["train_ready"] == 1
    assert result["gold_claims_present"] == 1
    assert "never expose" not in json.dumps(result)


def test_path_symlink_not_read(tmp_path):
    target = tmp_path / "original"
    target.write_bytes(b"some local private data")
    link = tmp_path / "link"
    link.symlink_to(target)
    assert audit_corpus._sha_file(link, {}) is None


def test_live_connection_disallows_parallel_sqlite(monkeypatch):
    monkeypatch.setattr(audit_corpus, "_engine_url", lambda: "sqlite+pysqlite:///:memory:")
    with pytest.raises(ValueError, match="PostgreSQL"):
        audit_corpus.audit_live_database(Path("/nonexistent"))


def test_command_exits_nonzero_for_protected_gold(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(audit_corpus, "audit_live_database", lambda _eis, _data: {
        "total_observations": 1,
        "checks": {"unapproved_gold_claim_present": 1},
    })
    assert audit_corpus.main(["--eis-root", str(tmp_path), "--expect-total", "1"]) == 2
    assert "unapproved_gold_claim_present" in capsys.readouterr().out


def test_command_exits_nonzero_for_unexpected_count(monkeypatch, capsys):
    monkeypatch.setattr(audit_corpus, "audit_live_database", lambda _eis, _data: {
        "total_observations": 74,
        "checks": {},
    })
    assert audit_corpus.main(["--expect-total", "75"]) == 2
    assert json.loads(capsys.readouterr().out)["total_observations"] == 74


def test_canonical_relative_report_path_is_restored_without_copy(tmp_path):
    source = tmp_path / "data" / "rag" / "reports" / "original.md"
    source.parent.mkdir(parents=True)
    source.write_text("local report fixture", encoding="utf-8")
    row = make_row(
        "relative", "analysis_run", "0123456789012345678",
        {"run_id": "real-existing", "report_path": "data/rag/reports/original.md"},
    )
    summary = audit_corpus.audit_observations(
        [row], {"real-existing"},
        eis_root=tmp_path / "data" / "tenders" / "eis",
        data_root=tmp_path,
    )
    assert summary["checks"]["saved_report_path_resolved_canonical_relative"] == 1
    assert summary["checks"]["linked_saved_analysis_runs"] == 1
    assert summary["checks"].get("saved_report_path_missing", 0) == 0


def test_canonical_relative_report_path_refuses_parent_traversal(tmp_path):
    row = make_row(
        "path-traversal", "analysis_run", "0123456789012345678",
        {"run_id": "real-existing", "report_path": "data/rag/reports/../../../../../sensitive"},
    )
    summary = audit_corpus.audit_observations(
        [row], {"real-existing"}, eis_root=tmp_path, data_root=tmp_path,
    )
    assert summary["checks"]["saved_report_path_missing"] == 1


def test_nested_blind_source_role_fails_closed(tmp_path):
    row = make_row(
        "nested-blind", "development_e2e", "0123456789012345678",
        {"source": {"source_role": "blind_holdout"}, "tags": ["blind_holdout"]},
    )
    result = audit_corpus.audit_observations([row], set(), eis_root=tmp_path)
    assert result["checks"]["protected_split_present"] == 1
