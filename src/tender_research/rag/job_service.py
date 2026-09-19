from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.tender_research.models import TenderAnalysisJob
from src.tender_research.rag.job_schemas import TenderAnalysisJobRecord, TenderJobStep


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_dumps(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_loads_dict(value: str | None) -> dict | None:
    if not value:
        return None
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else None


def _json_loads_list(value: str | None) -> list:
    if not value:
        return []
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []


def _normalize_messages(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def _normalize_step_status(value: str | None) -> str:
    mapping = {
        "in_progress": "running",
        "done": "completed",
        "completed_with_warning": "warning",
    }
    return mapping.get(str(value or "").strip().lower(), str(value or "pending").strip().lower() or "pending")


def _serialize_steps(steps: list[TenderJobStep | dict] | None) -> str | None:
    if steps is None:
        return None
    payload: list[dict] = []
    for step in steps:
        if isinstance(step, TenderJobStep):
            payload.append(step.to_dict())
        elif isinstance(step, dict):
            payload.append(
                {
                    "name": step.get("name", ""),
                    "title": step.get("title") or step.get("name", ""),
                    "status": _normalize_step_status(step.get("status")),
                    "progress_percent": int(step.get("progress_percent", 0) or 0),
                    "message": str(step.get("message", "") or ""),
                    "started_at": step.get("started_at"),
                    "finished_at": step.get("finished_at"),
                    "details": step.get("details"),
                }
            )
    return _json_dumps(payload)


def _deserialize_steps(value: str | None) -> list[TenderJobStep]:
    result: list[TenderJobStep] = []
    for item in _json_loads_list(value):
        if not isinstance(item, dict):
            continue
        result.append(
            TenderJobStep(
                name=str(item.get("name", "")),
                title=str(item.get("title") or item.get("name", "")),
                status=_normalize_step_status(item.get("status")),
                progress_percent=int(item.get("progress_percent", 0) or 0),
                message=str(item.get("message", "") or ""),
                started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
                finished_at=datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,
                details=item.get("details"),
            )
        )
    return result


def _row_to_record(row: TenderAnalysisJob) -> TenderAnalysisJobRecord:
    request_payload = _json_loads_dict(row.request_json)
    steps = _deserialize_steps(row.steps_json)
    current_section_title = None
    current_section_index = None
    total_sections = None
    for step in steps:
        details = step.details if isinstance(step.details, dict) else {}
        if step.status == "running" and step.name.startswith("section:"):
            current_section_title = str(details.get("section_title") or step.title or "")
            current_section_index = int(details.get("section_index", 0) or 0) or None
            total_sections = int(details.get("total_sections", 0) or 0) or None
            break
    return TenderAnalysisJobRecord(
        id=row.id,
        job_type=row.job_type,
        registry_number=row.registry_number,
        status=row.status,
        progress_percent=row.progress_percent,
        current_step=row.current_step,
        steps=steps,
        result=_json_loads_dict(row.result_json),
        warnings=_normalize_messages(_json_loads_list(row.warnings_json)),
        errors=_normalize_messages(_json_loads_list(row.errors_json)),
        report_path=row.report_path,
        analysis_run_id=row.analysis_run_id,
        created_at=_ensure_aware_utc(row.created_at),
        started_at=_ensure_aware_utc(row.started_at),
        finished_at=_ensure_aware_utc(row.finished_at),
        updated_at=_ensure_aware_utc(row.updated_at),
        duration_seconds=row.duration_seconds,
        source=row.source,
        request=request_payload,
        analysis_mode=(request_payload or {}).get("analysis_mode"),
        current_section_title=current_section_title,
        current_section_index=current_section_index,
        total_sections=total_sections,
    )


def create_job(
    session: Session,
    *,
    job_type: str,
    registry_number: str,
    request: dict,
    source: str = "api",
) -> TenderAnalysisJobRecord:
    now = _utcnow()
    row = TenderAnalysisJob(
        job_type=job_type,
        registry_number=registry_number,
        status="queued",
        progress_percent=0,
        current_step="queued",
        request_json=_json_dumps(request),
        source=source,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def get_job(session: Session, job_id: str) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    return _row_to_record(row)


def list_jobs(
    session: Session,
    *,
    registry_number: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TenderAnalysisJobRecord], int]:
    query = session.query(TenderAnalysisJob)
    if registry_number:
        query = query.filter(TenderAnalysisJob.registry_number == registry_number)
    if job_type:
        query = query.filter(TenderAnalysisJob.job_type == job_type)
    if status:
        query = query.filter(TenderAnalysisJob.status == status)
    total = query.count()
    rows = query.order_by(desc(TenderAnalysisJob.created_at)).offset(offset).limit(limit).all()
    return [_row_to_record(row) for row in rows], total


def _update_duration(row: TenderAnalysisJob) -> None:
    if row.started_at and row.finished_at:
        started_at = _ensure_aware_utc(row.started_at)
        finished_at = _ensure_aware_utc(row.finished_at)
        if started_at and finished_at:
            row.duration_seconds = max((finished_at - started_at).total_seconds(), 0.0)


def mark_job_running(session: Session, job_id: str) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    now = _utcnow()
    row.status = "running"
    row.started_at = row.started_at or now
    row.updated_at = now
    row.current_step = row.current_step or "running"
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def update_job_progress(
    session: Session,
    job_id: str,
    *,
    progress_percent: int,
    current_step: str,
    steps: list[TenderJobStep | dict] | None = None,
    message: str | None = None,
) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    now = _utcnow()
    row.status = "running"
    row.started_at = row.started_at or now
    row.updated_at = now
    row.progress_percent = max(0, min(100, int(progress_percent)))
    row.current_step = current_step
    if steps is not None:
        row.steps_json = _serialize_steps(steps)
    elif message:
        existing = _deserialize_steps(row.steps_json)
        if existing:
            for step in existing:
                if step.name == current_step:
                    step.message = message
                    step.status = "running"
                    step.progress_percent = row.progress_percent
            row.steps_json = _serialize_steps(existing)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def complete_job(
    session: Session,
    job_id: str,
    *,
    result: dict,
    warnings: list[str] | None = None,
    report_path: str | None = None,
    analysis_run_id: str | None = None,
    status: str | None = None,
    steps: list[TenderJobStep | dict] | None = None,
) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    now = _utcnow()
    normalized_warnings = _normalize_messages(warnings)
    row.status = status or ("completed_with_warnings" if normalized_warnings else "completed")
    row.progress_percent = 100
    row.finished_at = now
    row.updated_at = now
    row.result_json = _json_dumps(result)
    row.warnings_json = _json_dumps(normalized_warnings) if normalized_warnings else None
    row.errors_json = None
    row.report_path = report_path
    row.analysis_run_id = analysis_run_id
    row.current_step = "completed"
    if steps is not None:
        row.steps_json = _serialize_steps(steps)
    _update_duration(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def fail_job(
    session: Session,
    job_id: str,
    *,
    errors: list[str],
    warnings: list[str] | None = None,
    steps: list[TenderJobStep | dict] | None = None,
    current_step: str | None = None,
) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    now = _utcnow()
    row.status = "failed"
    row.finished_at = now
    row.updated_at = now
    row.errors_json = _json_dumps(_normalize_messages(errors))
    row.warnings_json = _json_dumps(_normalize_messages(warnings)) if warnings else None
    row.current_step = current_step or row.current_step or "failed"
    if steps is not None:
        row.steps_json = _serialize_steps(steps)
    _update_duration(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def cancel_job(session: Session, job_id: str) -> TenderAnalysisJobRecord | None:
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    now = _utcnow()
    row.status = "cancelled"
    row.finished_at = now
    row.updated_at = now
    row.current_step = "cancelled"
    _update_duration(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


TERMINAL_JOB_STATUSES = frozenset(
    {
        "completed",
        "completed_with_warnings",
        "cancelled",
    }
)


def is_terminal_job_status(status: str | None) -> bool:
    return str(status or "").strip().lower() in TERMINAL_JOB_STATUSES


def requeue_job(
    session: Session,
    job_id: str,
    *,
    warning: str,
) -> TenderAnalysisJobRecord | None:
    """Return a failed/running job to queued state for a bounded worker retry."""
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None:
        return None
    if is_terminal_job_status(row.status):
        return _row_to_record(row)
    warnings = _normalize_messages(_json_loads_list(row.warnings_json))
    normalized_warning = str(warning or "").strip()
    if normalized_warning and normalized_warning not in warnings:
        warnings.append(normalized_warning)
    row.status = "queued"
    row.current_step = "retry_wait"
    row.progress_percent = max(0, min(99, int(row.progress_percent or 0)))
    row.finished_at = None
    row.updated_at = _utcnow()
    row.errors_json = None
    row.warnings_json = _json_dumps(warnings) if warnings else None
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_record(row)


def touch_job_heartbeat(session: Session, job_id: str) -> bool:
    """Refresh only the durable liveness timestamp for a running worker job."""
    row = session.query(TenderAnalysisJob).filter(TenderAnalysisJob.id == job_id).first()
    if row is None or row.status != "running":
        return False
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    return True
