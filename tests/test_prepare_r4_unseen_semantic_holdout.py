"""Offline first-party candidate verification without exposing SUT predictions."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.acceptance.prepare_r4_unseen_semantic_holdout import (
    prepare_real_holdout,
)
from tests.test_r4_semantic_holdout import baseline, sha

N = "9000000000000000088"
T = "2026-10-14T20:00:00+00:00"


def case_files(tmp_path: Path):
    archive = tmp_path / "official.zip"
    original = tmp_path / "primary.docx"
    archive.write_bytes(b"First-party notice ZIP placeholder: mocked archive validation")
    original.write_bytes(b"First-party original document")
    receipt = [{
        "registry_number": N,
        "retrieval_provenance": "OFFICIAL_GETDOCSIP_TLS_VERIFIED",
        "official_archive_relpath": archive.name,
        "official_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "official_xml_sha256": sha("fresh official XML"),
        "documents": [{
            "relative_path": original.name,
            "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        }],
    }]
    return receipt


def run(candidates, tmp_path: Path):
    return prepare_real_holdout(
        candidates,
        source_root=tmp_path,
        development_audit=baseline(),
        source_set_id="unseen_holdout_trial",
        frozen_at_utc=T,
    )


def mock_official_zip(monkeypatch, receipt):
    def audit(path, notice_number):
        assert notice_number == N
        return {
            "zip_sha256": receipt[0]["official_zip_sha256"],
            "highest": {
                "xml_sha256": receipt[0]["official_xml_sha256"],
                "notice_type": "epNotificationEF2020",
            },
        }

    monkeypatch.setattr(
        "scripts.acceptance.prepare_r4_unseen_semantic_holdout.audit_archive", audit
    )


def test_source_bytes_and_official_type_before_lock(tmp_path, monkeypatch):
    receipt = case_files(tmp_path)
    mock_official_zip(monkeypatch, receipt)
    result = run(receipt, tmp_path)
    assert result["case_count"] == 1
    assert result["gold_freeze_status"] == "PENDING_INDEPENDENT_EXPERT"
    assert result["semantic_precision"] is None
    assert result["cases"][0]["registry_number"] == N


def test_absent_real_cases_fails_instead_of_fake_accuracy(tmp_path):
    with pytest.raises(ValueError, match="No previously unseen"):
        run([], tmp_path)


def test_untrusted_notice_receipt_fails_before_any_quality_claim(tmp_path, monkeypatch):
    receipt = case_files(tmp_path)
    mock_official_zip(monkeypatch, receipt)
    receipt[0]["retrieval_provenance"] = "MANUAL_UNKNOWN_SOURCE"
    with pytest.raises(ValueError, match="not independently attested"):
        run(receipt, tmp_path)


def test_changed_file_binary_and_root_escape_fail(tmp_path, monkeypatch):
    receipt = case_files(tmp_path)
    mock_official_zip(monkeypatch, receipt)
    (tmp_path / "primary.docx").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="bytes not attested"):
        run(receipt, tmp_path)
    receipt[0]["documents"][0]["relative_path"] = "../elsewhere.txt"
    with pytest.raises(ValueError, match="safe root-relative"):
        run(receipt, tmp_path)


def test_noncompetitive_doc_type_is_rejected(tmp_path, monkeypatch):
    receipt = case_files(tmp_path)
    monkeypatch.setattr(
        "scripts.acceptance.prepare_r4_unseen_semantic_holdout.audit_archive",
        lambda path, number: {
            "zip_sha256": receipt[0]["official_zip_sha256"],
            "highest": {
                "xml_sha256": receipt[0]["official_xml_sha256"],
                "notice_type": "epNotificationSingleSupplier",
            },
        },
    )
    with pytest.raises(ValueError, match="genuinely competitive"):
        run(receipt, tmp_path)
