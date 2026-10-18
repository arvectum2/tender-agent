"""Canonical archival getDocsIP proof: raw ZIP privately, only SHA in DB."""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.procurement_llm import collect_eis_official_archives as e
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.shared.db.base import Base

N = "0163200000326005243"
M = "0332100025426000039"
DATE = datetime(2026, 10, 18, 19, 0, tzinfo=UTC)


def zip_notice(number=N, version=2, kind="epNotificationEOK2020", inside=None):
    body = (
        f"<export><{kind}><commonInfo><purchaseNumber>"
        f"{inside or number}</purchaseNumber></commonInfo></{kind}></export>"
    ).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{kind}_{number}_{version}_01A0B2C3.xml", body)
        z.writestr("technical_attachment.txt", "External original binary, not learning gold" * 30)
    return buffer.getvalue()


def _prepared(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    engine = create_engine("sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3"))
    Base.metadata.create_all(engine)
    def engine_factory():
        return create_engine("sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3"))
    data = {N: zip_notice(), M: zip_notice(M, version=1)}
    def fetch(number):
        return data[number]
    return root, engine, engine_factory, fetch, data


def test_eis_sha_and_source_version_no_live_legal_claim(tmp_path):
    raw = zip_notice()
    path = tmp_path / "original.zip"
    record = e.make_eis_candidate(N, raw, DATE, path)
    payload = record["payload_json"]
    assert payload["official_archive_sha256"] == hashlib.sha256(raw).hexdigest()
    assert payload["selected_archived_notice_version"] == 2
    assert payload["archived_notice_type"] == "epNotificationEOK2020"
    assert payload["archived_notice_procedure_class"] == "COMPETITIVE_44FZ"
    assert payload["current_live_eis_verified"] is False
    assert payload["current_latest_notice_version_verified"] is False
    assert payload["owner_bid_go"] is False
    assert payload["human_verified_interpretation"] is False
    assert payload["training_labels"] == "NOT_REVIEWED"
    assert payload["raw_archive_bytes_in_db"] is False
    assert "External original binary" not in repr(record)
    assert record["event_kind"] == "manual_review"
    assert record["training_status"] == "candidate_unreviewed"


def test_eis_same_zip_bytes_and_changed_observation_time_idempotent(tmp_path):
    root, engine, factory, fetch, _ = _prepared(tmp_path)
    a = e.collect([N, M], fetch=fetch, root=root, apply=False, observed=DATE,
                  engine_factory=lambda: (_ for _ in ()).throw(AssertionError("DB use")))
    assert a["official_archives_verified"] == 2
    assert a["db_mutations"] == 0
    assert not list(root.rglob("*.zip"))
    applied = e.collect([N, M], fetch=fetch, root=root, apply=True,
                        observed=DATE, engine_factory=factory)
    assert applied["inserted"] == 2
    assert applied["new_private_original_zip_snapshots"] == 2
    with Session(engine) as session:
        records = session.query(ProcurementLearningObservation).all()
        assert len(records) == 2
        assert all(x.visibility_scope == "owner_internal" for x in records)
        assert all(x.training_status == "candidate_unreviewed" for x in records)
    later = e.collect([N, M], fetch=fetch, root=root, apply=True,
                      observed=DATE + timedelta(days=2), engine_factory=factory)
    assert later["inserted"] == 0
    assert later["existing"] == 2
    assert later["new_private_original_zip_snapshots"] == 0
    with Session(engine) as session:
        assert session.query(ProcurementLearningObservation).count() == 2
        assert all(x.payload_json["source_observed_at_utc"] == DATE.isoformat()
                   for x in session.query(ProcurementLearningObservation))
    engine.dispose()


@pytest.mark.parametrize("invalid", [
    [],
    ["1"],
    [N, N],
    ["ABC" + N],
    [N, M, N],
])
def test_bad_registry_allowlist_rejected(invalid):
    with pytest.raises(e.PublicOriginalError):
        e.validate_numbers(invalid)


@pytest.mark.parametrize("kind", [
    "epNotificationEOK2020",
    "epNotificationEZK2020",
    "epNotificationEF2020",
    "epNotificationEZT2020",
])
def test_all_supported_original_notice_kinds_can_be_recorded_without_legal_go(kind, tmp_path):
    raw = zip_notice(kind=kind)
    cand = e.make_eis_candidate(N, raw, DATE, tmp_path / "a.zip")
    assert cand["payload_json"]["current_live_eis_verified"] is False
    assert cand["payload_json"]["owner_bid_go"] is False
    if kind == "epNotificationEZT2020":
        assert cand["payload_json"]["archived_notice_procedure_class"] == "SINGLE_SUPPLIER_ART93_12"


def test_wrong_xml_purchase_number_or_zip_rejected(tmp_path):
    with pytest.raises(e.PublicOriginalError):
        e.make_eis_candidate(N, zip_notice(inside=M), DATE, tmp_path / "a.zip")
    with pytest.raises(e.PublicOriginalError):
        e.make_eis_candidate(N, b"Not ZIP" * 200, DATE, tmp_path / "b.zip")
    with pytest.raises(e.PublicOriginalError):
        e.make_eis_candidate(
            N, zip_notice(), datetime.fromisoformat("2026-10-18"), tmp_path / "c.zip"
        )


def test_failed_second_original_blocks_all_files_and_sql(tmp_path):
    root, engine, factory, fetch, data = _prepared(tmp_path)
    data[M] = zip_notice(M, inside=N)
    with pytest.raises(e.PublicOriginalError):
        e.collect([N, M], fetch=fetch, root=root, apply=True,
                  observed=DATE, engine_factory=factory)
    assert not list(root.rglob("*.zip"))
    with Session(engine) as db:
        assert db.query(ProcurementLearningObservation).count() == 0
    engine.dispose()


def test_failure_of_canonical_db_rollback_and_private_zip_cleanup(tmp_path, monkeypatch):
    root, engine, factory, fetch, _ = _prepared(tmp_path)
    def broken(_s, _row):
        raise RuntimeError("SQL inaccessible")
    monkeypatch.setattr(e, "append_candidate", broken)
    with pytest.raises(RuntimeError, match="inaccessible"):
        e.collect([N], fetch=fetch, root=root, apply=True,
                  observed=DATE, engine_factory=factory)
    assert not list(root.rglob("*.zip"))
    with Session(engine) as db:
        assert db.query(ProcurementLearningObservation).count() == 0
    engine.dispose()


def test_immutable_archive_existing_snapshot_cannot_be_overwritten(tmp_path):
    root, _, _, _, _ = _prepared(tmp_path)
    raw = zip_notice()
    path = e._original_path(root, N, raw)
    assert e._write_zip(path, raw, root)
    assert not e._write_zip(path, raw, root)
    path.chmod(0o644)
    with pytest.raises(e.PublicOriginalError, match="mismatch"):
        e._write_zip(path, raw, root)


def test_archive_member_conflict_not_accepted(tmp_path):
    raw = zip_notice(inside=M)
    with pytest.raises(e.PublicOriginalError):
        e.make_eis_candidate(N, raw, DATE, tmp_path / "original.zip")


def test_no_fabricated_archive_stage_on_empty_or_missing_live_notice():
    with pytest.raises(e.PublicOriginalError):
        e.classify_archive(N, b"")
