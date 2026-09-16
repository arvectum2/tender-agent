from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.document_ingestion.models import DocumentIngestionRun
from src.modules.ops_observability.schemas import (
    BackupMetric,
    DocumentFailureMetric,
    IngestionMetric,
    OperationalSnapshot,
    QueueMetric,
    StorageMetric,
    WorkerErrorMetric,
)
from src.shared.config.settings import get_settings
from src.shared.enums import DocumentIngestionRunStatus
from src.shared.storage.public import public_storage_snapshot
from src.tender_research.models import ProcurementTenderDocument, TenderAnalysisJob

QUEUE_WARNING_SECONDS = 10 * 60
QUEUE_CRITICAL_SECONDS = 30 * 60
INGESTION_WINDOW_HOURS = 24
DOCUMENT_WINDOW_HOURS = 24
WORKER_ERROR_WINDOW_MINUTES = 60
DOCUMENT_FAILURE_CRITICAL_COUNT = 10
WORKER_ERROR_CRITICAL_COUNT = 5
BACKUP_WARNING_SECONDS = 24 * 60 * 60
BACKUP_CRITICAL_SECONDS = 48 * 60 * 60


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    aware = _as_utc(value)
    if aware is None:
        return None
    return max(int((now - aware).total_seconds()), 0)


def _count(session: Session, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.scalar(statement) or 0)


def _queue_metric(session: Session, now: datetime) -> QueueMetric:
    queued = _count(session, TenderAnalysisJob, TenderAnalysisJob.status == "queued")
    running = _count(session, TenderAnalysisJob, TenderAnalysisJob.status == "running")
    oldest = session.scalar(
        select(func.min(TenderAnalysisJob.created_at)).where(TenderAnalysisJob.status == "queued")
    )
    oldest_age = _age_seconds(now, oldest)
    if oldest_age is not None and oldest_age >= QUEUE_CRITICAL_SECONDS:
        status, reason = "critical", "oldest_queued_job_exceeds_critical_threshold"
    elif oldest_age is not None and oldest_age >= QUEUE_WARNING_SECONDS:
        status, reason = "warning", "oldest_queued_job_exceeds_warning_threshold"
    else:
        status, reason = "ok", "queue_within_age_threshold"
    return QueueMetric(
        status=status,
        queued_depth=queued,
        running_count=running,
        oldest_queued_age_seconds=oldest_age,
        reason=reason,
    )


def _ingestion_metric(session: Session, now: datetime) -> IngestionMetric:
    window_start = now - timedelta(hours=INGESTION_WINDOW_HOURS)
    base = (DocumentIngestionRun.started_at >= window_start,)
    completed = _count(
        session,
        DocumentIngestionRun,
        *base,
        DocumentIngestionRun.run_status == DocumentIngestionRunStatus.COMPLETED,
    )
    partial = _count(
        session,
        DocumentIngestionRun,
        *base,
        DocumentIngestionRun.run_status == DocumentIngestionRunStatus.PARTIAL,
    )
    failed = _count(
        session,
        DocumentIngestionRun,
        *base,
        DocumentIngestionRun.run_status == DocumentIngestionRunStatus.FAILED,
    )
    started = _count(
        session,
        DocumentIngestionRun,
        *base,
        DocumentIngestionRun.run_status == DocumentIngestionRunStatus.STARTED,
    )
    observed = completed + partial + failed + started
    if observed == 0:
        status, reason = "unknown", "no_recent_ingestion_runs"
    elif failed >= 3:
        status, reason = "critical", "multiple_recent_ingestion_failures"
    elif failed or partial:
        status, reason = "warning", "recent_ingestion_not_fully_successful"
    else:
        status, reason = "ok", "recent_ingestion_runs_successful"
    return IngestionMetric(
        status=status,
        window_hours=INGESTION_WINDOW_HOURS,
        completed_count=completed,
        partial_count=partial,
        failed_count=failed,
        in_progress_count=started,
        reason=reason,
    )


def _document_failure_metric(session: Session, now: datetime) -> DocumentFailureMetric:
    window_start = now - timedelta(hours=DOCUMENT_WINDOW_HOURS)
    failed_downloads = _count(
        session,
        ProcurementTenderDocument,
        ProcurementTenderDocument.updated_at >= window_start,
        ProcurementTenderDocument.download_status == "failed",
    )
    failed_extractions = _count(
        session,
        ProcurementTenderDocument,
        ProcurementTenderDocument.updated_at >= window_start,
        ProcurementTenderDocument.text_extraction_status == "failed",
    )
    failures = failed_downloads + failed_extractions
    if failures >= DOCUMENT_FAILURE_CRITICAL_COUNT:
        status, reason = "critical", "document_failures_exceed_critical_threshold"
    elif failures:
        status, reason = "warning", "recent_document_processing_failures"
    else:
        status, reason = "ok", "no_recent_document_processing_failures"
    return DocumentFailureMetric(
        status=status,
        window_hours=DOCUMENT_WINDOW_HOURS,
        failed_download_count=failed_downloads,
        failed_extraction_count=failed_extractions,
        reason=reason,
    )


def _storage_metric() -> StorageMetric:
    try:
        snapshot = public_storage_snapshot()
    except Exception:  # noqa: BLE001 - dependency failure must surface as UNAVAILABLE
        return StorageMetric(status="unavailable", reason="storage_snapshot_unavailable")
    state = snapshot.state
    if state in {"critical", "ingestion_protected"}:
        status = "critical"
    elif state == "warning":
        status = "warning"
    elif state == "normal":
        status = "ok"
    else:
        status = "unknown"
    return StorageMetric(
        status=status,
        storage_state=state,
        used_percent=snapshot.used_percent,
        mount_verified=snapshot.mount_verified,
        ingestion_allowed=state not in {"ingestion_protected", "storage_unknown"},
        reason=snapshot.reason or f"storage_state_{state}",
    )


def _parse_backup_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return _as_utc(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _backup_metric(now: datetime) -> BackupMetric:
    root_raw = get_settings().arvectum_backup_root
    if not root_raw:
        return BackupMetric(status="unavailable", reason="backup_root_not_configured")
    root = Path(root_raw).expanduser()
    try:
        if not root.is_dir():
            return BackupMetric(status="unavailable", reason="backup_root_unavailable")
        candidates: list[tuple[datetime, str | None]] = []
        invalid_completed = False
        for child in root.iterdir():
            if child.is_symlink() or not child.is_dir():
                continue
            complete = child / "BACKUP_COMPLETE"
            manifest_path = child / "MANIFEST.json"
            if not complete.is_file():
                continue
            if not manifest_path.is_file():
                invalid_completed = True
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid_completed = True
                continue
            if manifest.get("schema_version") != "arv-076-backup-v1":
                invalid_completed = True
                continue
            created_at = _parse_backup_time(manifest.get("created_at"))
            if created_at is None:
                invalid_completed = True
                continue
            backup_id = manifest.get("backup_id") if isinstance(manifest.get("backup_id"), str) else None
            candidates.append((created_at, backup_id))
    except OSError:
        return BackupMetric(status="unavailable", reason="backup_root_unavailable")

    if not candidates:
        if invalid_completed:
            return BackupMetric(status="critical", reason="completed_backup_metadata_invalid")
        return BackupMetric(status="unknown", reason="no_completed_backup_found")

    created_at, backup_id = max(candidates, key=lambda item: item[0])
    age = _age_seconds(now, created_at)
    assert age is not None
    if age >= BACKUP_CRITICAL_SECONDS:
        status, reason = "critical", "latest_backup_exceeds_critical_age"
    elif age >= BACKUP_WARNING_SECONDS:
        status, reason = "warning", "latest_backup_exceeds_warning_age"
    else:
        status, reason = "ok", "latest_backup_within_age_threshold"
    return BackupMetric(
        status=status,
        latest_backup_created_at=created_at.isoformat(),
        latest_backup_age_seconds=age,
        latest_backup_id=backup_id,
        reason=reason,
    )


def _worker_error_metric(session: Session, now: datetime) -> WorkerErrorMetric:
    window_start = now - timedelta(minutes=WORKER_ERROR_WINDOW_MINUTES)
    failed_count = _count(
        session,
        TenderAnalysisJob,
        TenderAnalysisJob.status == "failed",
        TenderAnalysisJob.updated_at >= window_start,
    )
    latest = session.scalar(
        select(func.max(TenderAnalysisJob.updated_at)).where(
            TenderAnalysisJob.status == "failed",
            TenderAnalysisJob.updated_at >= window_start,
        )
    )
    latest_aware = _as_utc(latest)
    if failed_count >= WORKER_ERROR_CRITICAL_COUNT:
        status, reason = "critical", "recent_worker_failures_exceed_critical_threshold"
    elif failed_count:
        status, reason = "warning", "recent_worker_failures_present"
    else:
        status, reason = "ok", "no_recent_worker_failures"
    return WorkerErrorMetric(
        status=status,
        window_minutes=WORKER_ERROR_WINDOW_MINUTES,
        failed_job_count=failed_count,
        latest_failed_at=latest_aware.isoformat() if latest_aware else None,
        reason=reason,
    )


def _overall_status(statuses: list[str]) -> str:
    if "critical" in statuses:
        return "critical"
    if "warning" in statuses:
        return "warning"
    if any(status in {"unknown", "unavailable"} for status in statuses):
        return "unknown"
    return "ok"


def build_operational_snapshot(session: Session, *, now: datetime | None = None) -> OperationalSnapshot:
    generated = _as_utc(now) if now is not None else datetime.now(UTC)
    assert generated is not None
    queue = _queue_metric(session, generated)
    ingestion = _ingestion_metric(session, generated)
    document_failures = _document_failure_metric(session, generated)
    storage = _storage_metric()
    backup = _backup_metric(generated)
    worker_errors = _worker_error_metric(session, generated)
    statuses = [
        queue.status,
        ingestion.status,
        document_failures.status,
        storage.status,
        backup.status,
        worker_errors.status,
    ]
    return OperationalSnapshot(
        status=_overall_status(statuses),
        generated_at=generated.isoformat(),
        queue=queue,
        ingestion=ingestion,
        document_failures=document_failures,
        storage=storage,
        backup=backup,
        worker_errors=worker_errors,
    )
