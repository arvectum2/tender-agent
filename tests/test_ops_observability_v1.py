from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.modules.document_ingestion.models import DocumentIngestionRun
from src.modules.ops_observability import service as ops_service
from src.shared.enums import DocumentIngestionRunStatus
from src.shared.storage.public import PublicStorageSnapshot
from src.tender_research.models import TenderAnalysisJob

NOW = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)


def _storage(state: str = "normal") -> PublicStorageSnapshot:
    return PublicStorageSnapshot(
        filesystem_total_bytes=1000,
        filesystem_used_bytes=200,
        filesystem_free_bytes=800,
        used_percent=20.0,
        state=state,
        checked_at=NOW.isoformat(),
        mount_verified=state != "storage_unknown",
        reason=f"threshold_{state}" if state != "storage_unknown" else "storage_usage_unavailable",
    )


def _configure_backup(monkeypatch, tmp_path, *, age_hours: int = 1) -> None:
    backup = tmp_path / "20260916T050000Z-aabbccdd"
    backup.mkdir()
    (backup / "BACKUP_COMPLETE").write_text(NOW.isoformat(), encoding="utf-8")
    (backup / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "arv-076-backup-v1",
                "backup_id": backup.name,
                "created_at": (NOW - timedelta(hours=age_hours)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=str(tmp_path)),
    )


def _completed_ingestion(session) -> None:
    session.add(
        DocumentIngestionRun(
            ingestion_run_id="ING-OPS-001",
            document_set_id="DOCSET-OPS-001",
            run_status=DocumentIngestionRunStatus.COMPLETED,
            started_at=NOW - timedelta(minutes=20),
            finished_at=NOW - timedelta(minutes=19),
        )
    )
    session.commit()


def test_healthy_snapshot_uses_existing_state(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    _configure_backup(monkeypatch, tmp_path)
    _completed_ingestion(session)

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.schema_version == "ops-observability-v1"
    assert snapshot.status == "ok"
    assert snapshot.queue.status == "ok"
    assert snapshot.ingestion.status == "ok"
    assert snapshot.document_failures.status == "ok"
    assert snapshot.storage.status == "ok"
    assert snapshot.backup.status == "ok"
    assert snapshot.worker_errors.status == "ok"


def test_failed_ingestion_degrades_snapshot(monkeypatch, session):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )
    session.add(
        DocumentIngestionRun(
            ingestion_run_id="ING-OPS-FAILED",
            document_set_id="DOCSET-OPS-FAILED",
            run_status=DocumentIngestionRunStatus.FAILED,
            started_at=NOW - timedelta(minutes=20),
            finished_at=NOW - timedelta(minutes=19),
        )
    )
    session.commit()

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.ingestion.status == "warning"
    assert snapshot.ingestion.failed_count == 1
    assert snapshot.status == "warning"


def test_recent_worker_failure_degrades_snapshot(monkeypatch, session):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )
    session.add(
        TenderAnalysisJob(
            job_type="analyze",
            registry_number="OPS-FAIL",
            status="failed",
            created_at=NOW - timedelta(minutes=10),
            updated_at=NOW - timedelta(minutes=2),
        )
    )
    session.commit()

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.worker_errors.status == "warning"
    assert snapshot.worker_errors.failed_job_count == 1
    assert snapshot.status == "warning"


def test_stale_queue_is_critical(monkeypatch, session):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )
    session.add(
        TenderAnalysisJob(
            job_type="prepare",
            registry_number="OPS-STALE",
            status="queued",
            created_at=NOW - timedelta(minutes=31),
            updated_at=NOW - timedelta(minutes=31),
        )
    )
    session.commit()

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.queue.status == "critical"
    assert snapshot.queue.queued_depth == 1
    assert snapshot.queue.oldest_queued_age_seconds == 31 * 60
    assert snapshot.status == "critical"


def test_storage_ingestion_guard_is_critical(monkeypatch, session):
    monkeypatch.setattr(
        ops_service,
        "public_storage_snapshot",
        lambda: _storage("ingestion_protected"),
    )
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.storage.status == "critical"
    assert snapshot.storage.ingestion_allowed is False
    assert snapshot.status == "critical"


def test_stale_backup_age_is_warning(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    _configure_backup(monkeypatch, tmp_path, age_hours=25)
    _completed_ingestion(session)

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.backup.status == "warning"
    assert snapshot.backup.latest_backup_age_seconds == 25 * 60 * 60
    assert snapshot.status == "warning"


def test_unavailable_dependencies_are_explicit_not_zero(monkeypatch, session):
    def fail_storage():
        raise OSError("storage probe unavailable")

    monkeypatch.setattr(ops_service, "public_storage_snapshot", fail_storage)
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )

    snapshot = ops_service.build_operational_snapshot(session, now=NOW)

    assert snapshot.storage.status == "unavailable"
    assert snapshot.storage.used_percent is None
    assert snapshot.backup.status == "unavailable"
    assert snapshot.backup.latest_backup_age_seconds is None
    assert snapshot.ingestion.status == "unknown"
    assert snapshot.status == "unknown"


def test_ops_observability_endpoint_exposes_versioned_contract(monkeypatch, client):
    monkeypatch.setattr(ops_service, "public_storage_snapshot", lambda: _storage())
    monkeypatch.setattr(
        ops_service,
        "get_settings",
        lambda: SimpleNamespace(arvectum_backup_root=None),
    )

    response = client.get("/api/ops/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "ops-observability-v1"
    assert payload["status"] == "unknown"
    assert set(payload) == {
        "schema_version",
        "status",
        "generated_at",
        "queue",
        "ingestion",
        "document_failures",
        "storage",
        "backup",
        "worker_errors",
    }
