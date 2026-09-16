from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

MetricStatus = Literal["ok", "warning", "critical", "unknown", "unavailable"]
OverallStatus = Literal["ok", "warning", "critical", "unknown"]


class QueueMetric(BaseModel):
    status: MetricStatus
    queued_depth: int
    running_count: int
    oldest_queued_age_seconds: int | None = None
    reason: str


class IngestionMetric(BaseModel):
    status: MetricStatus
    window_hours: int
    completed_count: int
    partial_count: int
    failed_count: int
    in_progress_count: int
    reason: str


class DocumentFailureMetric(BaseModel):
    status: MetricStatus
    window_hours: int
    failed_download_count: int
    failed_extraction_count: int
    reason: str


class StorageMetric(BaseModel):
    status: MetricStatus
    storage_state: str | None = None
    used_percent: float | None = None
    mount_verified: bool | None = None
    ingestion_allowed: bool | None = None
    reason: str


class BackupMetric(BaseModel):
    status: MetricStatus
    latest_backup_created_at: str | None = None
    latest_backup_age_seconds: int | None = None
    latest_backup_id: str | None = None
    reason: str


class WorkerErrorMetric(BaseModel):
    status: MetricStatus
    window_minutes: int
    failed_job_count: int
    latest_failed_at: str | None = None
    reason: str


class OperationalSnapshot(BaseModel):
    schema_version: Literal["ops-observability-v1"] = "ops-observability-v1"
    status: OverallStatus
    generated_at: str
    queue: QueueMetric
    ingestion: IngestionMetric
    document_failures: DocumentFailureMetric
    storage: StorageMetric
    backup: BackupMetric
    worker_errors: WorkerErrorMetric
