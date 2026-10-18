"""Candidate capture does not make legal gold or duplicate primary sources."""
from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    digest,
    make_analysis_candidate,
    make_legacy_candidate,
    make_manual_candidate,
)
from src.tender_research.rag.history_service import record_analysis_run


def manual(event_id="manual-test-00001"):
    return {
        "event_id": event_id,
        "procurement_ref": "0372200172326000015",
        "participation": "submitted",
        "participation_evidence": "owner_reported_not_protocol",
        "review_state": "owner_reported",
        "source_links": [],
    }


def test_manual_append_only_replay_and_conflict(session):
    item = make_manual_candidate(manual())
    assert append_candidate(session, item)
    assert not append_candidate(session, item)
    event = manual()
    event["review_summary"] = "changed"
    with pytest.raises(ValueError, match="Immutable"):
        append_candidate(session, make_manual_candidate(event))
    session.rollback()
    # No external files are copied, all data remains in the caller-owned DB.
    assert session.query(ProcurementLearningObservation).count() == 0


def test_blind_and_gold_protected(session):
    for extra in ({"protected_blind": True}, {"signed_human_gold": True}, {"legal_gold": True}):
        event = dict(manual(), **extra)
        with pytest.raises(ValueError):
            append_candidate(session, make_manual_candidate(event))
    event = manual()
    row = make_manual_candidate(event)
    row["candidate_split"] = "blind_holdout"
    with pytest.raises(ValueError):
        append_candidate(session, row)
    row["training_status"] = "train_ready"
    with pytest.raises(ValueError):
        append_candidate(session, row)
    assert session.query(ProcurementLearningObservation).count() == 0


def test_participation_evidence_and_customer_scope(session):
    event = manual()
    del event["participation_evidence"]
    with pytest.raises(ValueError, match="evidence"):
        append_candidate(session, make_manual_candidate(event))
    event = manual()
    row = make_manual_candidate(event, customer_id="tenant-a")
    assert row["visibility_scope"] == "tenant"
    assert append_candidate(session, row)
    row2 = make_manual_candidate(manual("manual-test-00002"), customer_id="tenant-b")
    assert append_candidate(session, row2)
    listed = session.scalars(select(ProcurementLearningObservation).where(
        ProcurementLearningObservation.customer_id == "tenant-a"
    )).all()
    assert len(listed) == 1
    assert listed[0].procurement_ref == event["procurement_ref"]
    assert session.query(ProcurementLearningObservation).count() == 2


def test_owner_cannot_impersonate_tenant(session):
    item = make_manual_candidate(manual())
    item["customer_id"] = "tenant-a"
    with pytest.raises(ValueError, match="impersonate"):
        append_candidate(session, item)


def test_legacy_id_validation_and_payload_preserved(session):
    payload = manual()
    identity = {"kind": "manual_review", "event_id": payload["event_id"]}
    legacy = {
        "observation_id": digest(identity), "kind": "manual_review",
        "procurement_ref": payload["procurement_ref"],
        "participation": "submitted", "review_state": "owner_reported",
        "provenance_sha256": "0" * 64,
        "candidate_split": "manual_candidate_not_blind",
        "training_status": "candidate_unreviewed",
        "payload": json.dumps(payload, ensure_ascii=False),
    }
    item = make_legacy_candidate(legacy)
    assert append_candidate(session, item)
    assert not append_candidate(session, item)
    assert session.get(ProcurementLearningObservation, item["observation_id"]).payload_json == payload
    wrong = deepcopy(legacy)
    wrong["observation_id"] = "1" * 64
    with pytest.raises(ValueError, match="identity"):
        make_legacy_candidate(wrong)


def test_saved_analysis_run_hook_explicitly_disabled(session, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "0")
    result = record_analysis_run(
        session, registry_number="0123456789012345678", status="completed",
        used_llm=True, llm_model="gemma4", source="local",
    )
    assert result.id
    assert session.query(ProcurementLearningObservation).count() == 0


def test_owner_authorized_future_capture_defaults_on(session, monkeypatch):
    from src.modules.procurement_learning_corpus.service import learning_capture_enabled

    monkeypatch.delenv("TENDER_LEARNING_CAPTURE_ENABLED", raising=False)
    assert learning_capture_enabled() is True
    run = record_analysis_run(
        session, registry_number="0123456789012345678",
        status="completed", used_llm=True, llm_model="gemma4", source="local",
    )
    assert session.query(ProcurementLearningObservation).count() == 1
    assert session.query(ProcurementLearningObservation).one().payload_json["run_id"] == run.id


def test_invalid_capture_env_cannot_silently_suppress_db_ingestion(session, monkeypatch):
    from src.modules.procurement_learning_corpus.service import learning_capture_enabled

    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "off")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        learning_capture_enabled()
    with pytest.raises(ValueError, match="must be 0 or 1"):
        record_analysis_run(
            session, registry_number="0123456789012345678",
            status="completed", used_llm=True, llm_model="gemma4", source="local",
        )
    session.rollback()
    assert session.query(ProcurementLearningObservation).count() == 0


def test_saved_analysis_run_hook_enabled(session, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "1")
    result = record_analysis_run(
        session, registry_number="0123456789012345678", status="completed",
        used_llm=True, llm_model="gemma4", source="local",
    )
    rows = session.query(ProcurementLearningObservation).all()
    assert len(rows) == 1
    assert rows[0].payload_json["run_id"] == result.id
    assert rows[0].training_status == "candidate_unreviewed"
    assert rows[0].visibility_scope == "owner_internal"
    assert not append_candidate(session, make_analysis_candidate(result))


def test_analysis_run_requires_saved_id():
    with pytest.raises(ValueError, match="Saved run"):
        make_analysis_candidate(SimpleNamespace(id=None))


def test_legacy_import_from_existing_sqlite_read_only(tmp_path):
    from scripts.procurement_llm.import_candidates import _legacy_items

    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE observations (observation_id TEXT, kind TEXT, procurement_ref TEXT, "
            "participation TEXT, review_state TEXT, provenance_sha256 TEXT, candidate_split TEXT, "
            "training_status TEXT, payload TEXT)"
        )
        payload = manual()
        conn.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)",
            (digest({"kind": "manual_review", "event_id": payload["event_id"]}),
             "manual_review", payload["procurement_ref"], "submitted", "owner_reported", "f" * 64,
             "manual_candidate_not_blind", "candidate_unreviewed", json.dumps(payload)),
        )
    one = _legacy_items(db)
    assert len(one) == 1
    assert one[0]["payload_json"]["event_id"] == payload["event_id"]


def test_operator_manual_cli_is_dry_run_by_default(tmp_path, capsys):
    from scripts.procurement_llm.import_candidates import main

    file = tmp_path / "manual.json"
    file.write_text(json.dumps(manual()), encoding="utf-8")
    assert main(["--manual-file", str(file)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"mode": "dry_run", "candidates": 1, "unique_ids": 1}


def test_operator_cli_refuses_apply_without_database_confirmation(tmp_path):
    from scripts.procurement_llm.import_candidates import main

    file = tmp_path / "manual.json"
    file.write_text(json.dumps(manual()), encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        main(["--manual-file", str(file), "--apply"])


def test_operator_cli_refuses_parallel_sqlite_store(monkeypatch):
    from scripts.procurement_llm.import_candidates import _engine_url

    monkeypatch.setenv("AI_CORP_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    with pytest.raises(ValueError, match="Only existing PostgreSQL"):
        _engine_url()


def test_alembic_downgrade_blocks_real_observations(session):
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[2] / "migrations/versions/107_add_procurement_learning_observations.py"
    spec = importlib.util.spec_from_file_location("migration_procurement_learning_107", module_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration._assert_empty_before_downgrade(session.connection())
    assert append_candidate(session, make_manual_candidate(manual("manual-test-downgrade")))
    with pytest.raises(RuntimeError, match="populated canonical procurement evidence"):
        migration._assert_empty_before_downgrade(session.connection())


def test_manual_stdin_can_validate_without_any_db_access(monkeypatch, capsys):
    import io

    from scripts.procurement_llm.import_candidates import main

    raw = json.dumps(manual("manual-chat-20261016-001")).encode()
    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(raw), isatty=lambda: False))
    monkeypatch.setenv("AI_CORP_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    assert main(["--manual-stdin"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["candidates"] == 1
    assert result["mode"] == "dry_run"


def test_manual_stdin_rejects_blind_and_gold_even_in_dry_run(monkeypatch):
    import io

    from scripts.procurement_llm.import_candidates import main

    for flag in ("signed_human_gold", "protected_blind"):
        case = manual("manual-chat-20261016-002")
        case[flag] = True
        monkeypatch.setattr(
            "sys.stdin",
            SimpleNamespace(buffer=io.BytesIO(json.dumps(case).encode()), isatty=lambda: False),
        )
        with pytest.raises(ValueError, match="gold|blind"):
            main(["--manual-stdin"])


def test_manual_stdin_rejects_oversize_without_db_access(monkeypatch):
    import io

    from scripts.procurement_llm.import_candidates import main

    huge = json.dumps({**manual("manual-chat-20261016-003"), "blob": "x" * 65536})
    monkeypatch.setattr(
        "sys.stdin",
        SimpleNamespace(buffer=io.BytesIO(huge.encode()), isatty=lambda: False),
    )
    with pytest.raises(SystemExit, match="2"):
        main(["--manual-stdin"])
