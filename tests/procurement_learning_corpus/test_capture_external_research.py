"""Future external ChatGPT procurement research uses ONLY canonical PG candidate model."""
from __future__ import annotations

import copy
import hashlib
import json
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.procurement_llm import capture_external_research as capture
from scripts.procurement_llm.capture_external_research import (
    ExternalCaptureError,
    _manifest_file,
    build_candidate,
    main,
)
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import append_candidate
from src.shared.db.base import Base


def create_fixture(tmp_path, *, original=True):
    note = tmp_path / "analysis-001.md"
    note.write_text("# Procurement research\nCorporate web project, unverified.", encoding="utf8")
    note.chmod(0o600)
    source = tmp_path / "original-public.html"
    source.write_bytes(b"<html>Public market source, status not verified</html>")
    source.chmod(0o600)
    status = "ORIGINAL_SHA_VERIFIED" if original else "PUBLIC_URL_UNVERIFIED"
    manifest = {
        "schema": "external_chatgpt_procurement_research_v1",
        "procurement_ref": "workspace:19006",
        "source_platform": "workspace",
        "original_source_url": (
            "https://workspace.ru/tenders/"
            "sozdanie-i-dalneyshee-razvitie-sayta-kompanii-19006/"
        ),
        "original_source_status": status,
        "original_source_path": str(source) if original else None,
        "original_source_sha256": (
            hashlib.sha256(source.read_bytes()).hexdigest() if original else None
        ),
        "analysis_artifact_path": str(note),
        "analyst": "chatgpt",
        "model_label": "GPT-6 manual independent source analysis",
        "observed_at_utc": "2026-10-18T21:20:00+03:00",
        "standalone_sanitized_analysis": True,
    }
    return manifest, note, source


def test_source_sha_verified_and_raw_artifact_not_in_db(tmp_path):
    manifest, analysis, original = create_fixture(tmp_path)
    before = copy.deepcopy(manifest)
    result = build_candidate(manifest, private_root=tmp_path)
    assert manifest == before
    assert result["event_kind"] == "manual_review"
    assert result["visibility_scope"] == "owner_internal"
    assert result["training_status"] == "candidate_unreviewed"
    assert result["candidate_split"] == "manual_candidate_not_blind"
    assert result["review_state"] == "source_documented"
    assert result["payload_json"]["original_verification_gate"] == (
        "PRIVATE_ORIGINAL_BYTES_SHA_ATTESTED_NOT_LEGAL_GOLD"
    )
    assert result["payload_json"]["original_source_bytes_sha256"] == hashlib.sha256(
        original.read_bytes()
    ).hexdigest()
    assert result["payload_json"]["analysis_artifact_sha256"] == hashlib.sha256(
        analysis.read_bytes()
    ).hexdigest()
    assert result["payload_json"]["owner_bid_go"] is False
    assert result["payload_json"]["human_verified_interpretation"] is False
    assert result["payload_json"]["training_labels"] == "NOT_REVIEWED"
    payload = json.dumps(result["payload_json"], ensure_ascii=False)
    assert "Corporate web project, unverified" not in payload
    assert "Public market source, status not verified" not in payload
    assert manifest["original_source_url"] not in payload


def test_public_only_source_does_not_impersonate_verified_original(tmp_path):
    m, _, _ = create_fixture(tmp_path, original=False)
    c = build_candidate(m, private_root=tmp_path)
    assert c["review_state"] == "unverified_chat_recall"
    assert c["payload_json"]["original_source_bytes_sha256"] is None
    assert c["payload_json"]["original_verification_gate"] == (
        "PUBLIC_URL_ONLY_ORIGINAL_NOT_VERIFIED"
    )


def test_append_once_and_new_analysis_version(session, tmp_path):
    m, note, _ = create_fixture(tmp_path)
    one = build_candidate(m, private_root=tmp_path)
    assert append_candidate(session, one)
    assert not append_candidate(session, one)
    note.write_text("# Procurement updated local research", encoding="utf8")
    two = build_candidate(m, private_root=tmp_path)
    assert two["observation_id"] != one["observation_id"]
    assert append_candidate(session, two)
    assert session.query(ProcurementLearningObservation).count() == 2
    assert all(
        r.training_status == "candidate_unreviewed"
        for r in session.query(ProcurementLearningObservation)
    )


@pytest.mark.parametrize(("key", "value"), [
    ("analyst", "tender_agent"),
    ("model_label", ""),
    ("observed_at_utc", "2026-10-18T21:20:00"),
    ("source_platform", "unauthorized_platform"),
    ("original_source_status", "SIGNED_HUMAN_GOLD"),
    ("original_source_url", "https://evil.example/tenders/a-19006/"),
    ("original_source_url", "http://workspace.ru/tenders/a-19006/"),
    ("original_source_url", "https://user:password@workspace.ru/tenders/a-19006/"),
    ("original_source_url", "https://workspace.ru/tenders/a-19006/?token=secret"),
    ("original_source_url", "https://workspace.ru/tenders/a-19006/#secret"),
    ("original_source_url", "https://workspace.ru/tenders/a-19007/"),
    ("original_source_url", "https://127.0.0.1/tenders/a-19006/"),
    ("original_source_sha256", "0" * 64),
    ("original_source_sha256", "broken"),
    ("standalone_sanitized_analysis", False),
])
def test_unsafe_or_fake_provenance_rejected(tmp_path, key, value):
    manifest, _, _ = create_fixture(tmp_path)
    manifest[key] = value
    with pytest.raises(ExternalCaptureError):
        build_candidate(manifest, private_root=tmp_path)


def test_url_unverified_cannot_claim_partial_hash(tmp_path):
    m, _, _ = create_fixture(tmp_path, original=False)
    m["original_source_sha256"] = "a" * 64
    with pytest.raises(ExternalCaptureError):
        build_candidate(m, private_root=tmp_path)


def test_original_different_doc_modified_before_import_fails(tmp_path):
    m, _, f = create_fixture(tmp_path)
    f.write_bytes(b"Tampered")
    with pytest.raises(ExternalCaptureError, match="does not match"):
        build_candidate(m, private_root=tmp_path)


def test_manifest_must_not_allow_gold_field(tmp_path):
    m, _, _ = create_fixture(tmp_path)
    m["legal_gold"] = True
    with pytest.raises(ExternalCaptureError):
        build_candidate(m, private_root=tmp_path)


def test_artifact_file_must_be_private_and_not_symlink(tmp_path):
    m, file, _ = create_fixture(tmp_path)
    file.chmod(0o644)
    with pytest.raises(ExternalCaptureError, match="permissions"):
        build_candidate(m, private_root=tmp_path)
    file.chmod(0o600)
    link = tmp_path / "symlink.md"
    link.symlink_to(file)
    m["analysis_artifact_path"] = str(link)
    with pytest.raises(ExternalCaptureError, match="unsafe"):
        build_candidate(m, private_root=tmp_path)


def test_path_outside_owner_root_rejected(tmp_path):
    m, _, _ = create_fixture(tmp_path)
    m["analysis_artifact_path"] = __file__
    with pytest.raises(ExternalCaptureError):
        build_candidate(m, private_root=tmp_path)


def test_eis_url_regnumber_public_allowlist(tmp_path):
    m, _, _ = create_fixture(tmp_path, original=False)
    m.update({
        "procurement_ref": "0163200000326005243",
        "source_platform": "eis",
        "original_source_url": (
            "https://zakupki.gov.ru/epz/order/notice/ok20/view/"
            "printForm.html?regNumber=0163200000326005243"
        ),
    })
    c = build_candidate(m, private_root=tmp_path)
    assert c["payload_json"]["source_host"] == "zakupki.gov.ru"
    m["original_source_url"] += "&access_token=secret"
    with pytest.raises(ExternalCaptureError):
        build_candidate(m, private_root=tmp_path)


def test_b2b_number_must_match_exact_original_url(tmp_path):
    m, _, _ = create_fixture(tmp_path, original=False)
    m.update({
        "procurement_ref": "b2bcenter:4632891",
        "source_platform": "b2bcenter",
        "original_source_url": (
            "https://www.b2b-center.ru/app/market-next/rfi-crm/tender-4632891/"
        ),
    })
    assert build_candidate(m, private_root=tmp_path)
    m["original_source_url"] = m["original_source_url"].replace("4632891", "4632892")
    with pytest.raises(ExternalCaptureError):
        build_candidate(m, private_root=tmp_path)


def test_private_manifest_cannot_contain_duplicate_json_keys(tmp_path):
    file = tmp_path / "duplicate.json"
    file.write_text('{"a":1,"a":2}', encoding="utf8")
    file.chmod(0o600)
    with pytest.raises(ExternalCaptureError, match="duplicate"):
        _manifest_file(file, root=tmp_path)


def test_explicit_apply_to_existing_store_only_and_idempotent(tmp_path, monkeypatch, capsys):
    manifest, _, _ = create_fixture(tmp_path)
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf8")
    p.chmod(0o600)
    engine = create_engine("sqlite+pysqlite:///" + str(tmp_path / "test.sqlite3"))
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(capture, "OWNER_PRIVATE", tmp_path)
    monkeypatch.setattr(capture, "_engine_url", lambda: "sqlite+pysqlite:///" + str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(sys, "argv", ["capture", "--manifest", str(p)])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["database_mutations"] == 0

    monkeypatch.setattr(sys, "argv", ["capture", "--manifest", str(p), "--apply", "--confirm-database", "arvectum"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["inserted"] == 1
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["existing"] == 1
    with Session(create_engine("sqlite+pysqlite:///" + str(tmp_path / "test.sqlite3"))) as s:
        assert s.query(ProcurementLearningObservation).count() == 1


def test_apply_requires_explicit_database_confirmation(tmp_path, monkeypatch):
    m, _, _ = create_fixture(tmp_path)
    f = tmp_path / "testmanifest.json"
    f.write_text(json.dumps(m), encoding="utf8")
    f.chmod(0o600)
    monkeypatch.setattr(capture, "OWNER_PRIVATE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["capture", "--manifest", str(f), "--apply"])
    with pytest.raises(SystemExit, match="2"):
        main()
