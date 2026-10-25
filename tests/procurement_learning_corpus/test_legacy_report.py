"""Source-only legacy report artifacts are not saved analysis runs or human gold."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select

from scripts.procurement_llm import import_candidates
from scripts.procurement_llm.audit_corpus import audit_observations
from src.modules.procurement_learning_corpus.legacy_report import (
    make_unlinked_legacy_report_candidate,
)
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import append_candidate

REG = "0323100010326000013"
NAME = f"analyze_tender_{REG}_20260705T195400298896Z_09d21c02.md"


def original(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "data" / "rag" / "reports"
    root.mkdir(parents=True)
    file = root / NAME
    file.write_bytes(b"# Original saved historical report\nnot a trained answer\n")
    return file, root, sha256(file.read_bytes()).hexdigest()


def test_index_only_sha_bound_metadata_and_idempotent_replay(tmp_path, session):
    path, root, digest = original(tmp_path)
    row = make_unlinked_legacy_report_candidate(path, expected_sha256=digest, reports_root=root)
    assert row["event_kind"] == "legacy_report_artifact"
    assert row["procurement_ref"] == REG
    assert row["participation"] == "unknown"
    assert row["training_status"] == "candidate_unreviewed"
    assert row["payload_json"]["historical_saved_run_id"] is None
    assert row["payload_json"]["historical_run_identity_verified"] is False
    assert row["payload_json"]["original_full_report_copied_to_db"] is False
    assert "not a trained answer" not in str(row)
    assert append_candidate(session, row)
    assert not append_candidate(session, row)
    assert session.query(ProcurementLearningObservation).count() == 1
    item = session.scalars(select(ProcurementLearningObservation)).one()
    assert item.source_ref.startswith("canonical_legacy_report:")
    assert item.visibility_scope == "owner_internal"


def test_bad_sha_and_modified_report_rejected(tmp_path):
    path, root, digest = original(tmp_path)
    with pytest.raises(ValueError, match="does not match"):
        make_unlinked_legacy_report_candidate(path, expected_sha256="a" * 64, reports_root=root)
    path.write_bytes(b"changed historical evidence")
    with pytest.raises(ValueError, match="does not match"):
        make_unlinked_legacy_report_candidate(path, expected_sha256=digest, reports_root=root)


def test_symlink_traversal_and_bad_filename_are_rejected(tmp_path):
    path, root, digest = original(tmp_path)
    outside = tmp_path / "outside" / NAME
    outside.parent.mkdir()
    outside.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="existing report root"):
        make_unlinked_legacy_report_candidate(outside, expected_sha256=digest, reports_root=root)
    link = root / ("analyze_tender_" + REG + "_20260705T200000000000Z_deadbeef.md")
    link.symlink_to(path)
    with pytest.raises(ValueError, match="symlinked"):
        make_unlinked_legacy_report_candidate(link, expected_sha256=digest, reports_root=root)
    wrong = root / "unstructured-unknown.md"
    wrong.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="basename"):
        make_unlinked_legacy_report_candidate(wrong, expected_sha256=digest, reports_root=root)


def test_empty_and_invalid_sha_are_rejected(tmp_path):
    path, root, _ = original(tmp_path)
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="Invalid original report size"):
        make_unlinked_legacy_report_candidate(
            path, expected_sha256=sha256(b"").hexdigest(), reports_root=root
        )
    with pytest.raises(ValueError, match="Expected a 64-digit SHA256"):
        make_unlinked_legacy_report_candidate(path, expected_sha256="invalid", reports_root=root)


def test_auditor_sha_read_back_not_a_fake_saved_run(tmp_path):
    path, root, digest = original(tmp_path)
    row = make_unlinked_legacy_report_candidate(path, expected_sha256=digest, reports_root=root)
    summary = audit_observations([row], set(), eis_root=tmp_path / "eis")
    assert summary["kinds"] == {"legacy_report_artifact": 1}
    assert summary["checks"]["legacy_artifact_sha_verified"] == 1
    assert summary["checks"]["legacy_artifact_unlinked_run_id"] == 1
    assert summary["checks"].get("unknown_kind", 0) == 0
    assert summary["train_ready"] == 0


def test_cli_protects_confirmation_and_SHA_pairing(monkeypatch, capsys, tmp_path):
    path, root, digest = original(tmp_path)
    monkeypatch.setattr(
        "src.modules.procurement_learning_corpus.legacy_report.CANONICAL_REPORT_ROOT", root
    )
    # Explicit CLI always uses the real ArvectumSSD source root. Tests must
    # exercise malformed args without touching canonical disk or any DB.
    with pytest.raises(SystemExit, match="2"):
        import_candidates.main(["--legacy-report-file", str(path)])
    with pytest.raises(SystemExit, match="2"):
        import_candidates.main([
            "--legacy-report-file", str(path), "--expected-report-sha256", digest,
            "--apply"
        ])
    assert "usage:" in capsys.readouterr().err
