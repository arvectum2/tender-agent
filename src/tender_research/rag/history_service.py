from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc
from sqlalchemy.orm import Session

# TenderAnalysisRun has optional foreign keys into the customer-pilot contour.
# Register those tables even when analysis is invoked directly (CLI/library)
# rather than through src.main / src.shared.db.models.
from src.modules.customer_pilot import models as _customer_pilot_models  # noqa: F401
from src.modules.customer_registry import (
    models as _customer_registry_models,  # noqa: F401
)
from src.tender_research.models import TenderAnalysisRun

logger = logging.getLogger(__name__)

_REPORTS_DIR_NAME = "rag"
_REPORTS_SUBDIR = "reports"
_SOURCE_MAX_LENGTH = 32


def _safe_reports_dir(data_dir: str) -> Path:
    raw = Path(data_dir) / _REPORTS_DIR_NAME / _REPORTS_SUBDIR
    return raw.resolve()


def _resolve_report_path(report_path: str | None, data_dir: str) -> str | None:
    if not report_path:
        return None
    candidate = (Path(data_dir).parent / report_path).resolve() if not Path(report_path).is_absolute() else Path(report_path).resolve()
    allowed = _safe_reports_dir(data_dir)
    try:
        candidate.relative_to(allowed)
    except ValueError:
        logger.warning("Path traversal blocked: %s is outside %s", candidate, allowed)
        return None
    if not candidate.exists():
        return None
    return str(candidate)


def _generate_preview(text: str, max_chars: int = 1500) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars].rsplit(" ", 1)[0] + "..."


class AnalysisRunRecord:
    def __init__(self, row: TenderAnalysisRun):
        self.id: str = row.id
        self.registry_number: str = row.registry_number
        self.status: str = row.status
        self.used_llm: bool = row.used_llm
        self.llm_model: str | None = row.llm_model
        self.retrieval_provider: str | None = row.retrieval_provider
        self.retrieval_model: str | None = row.retrieval_model
        self.sections_count: int = row.sections_count
        self.sources_count: int = row.sources_count
        self.report_path: str | None = row.report_path
        self.report_markdown_preview: str | None = row.report_markdown_preview
        self.warnings: list[str] = json.loads(row.warnings_json) if row.warnings_json else []
        self.errors: list[str] = json.loads(row.errors_json) if row.errors_json else []
        self.duration_seconds: float | None = row.duration_seconds
        self.source: str | None = row.source
        self.metadata: dict = json.loads(row.metadata_json) if row.metadata_json else {}
        self.created_at: datetime = row.created_at
        self.updated_at: datetime | None = row.updated_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "registry_number": self.registry_number,
            "status": self.status,
            "used_llm": self.used_llm,
            "llm_model": self.llm_model,
            "retrieval_provider": self.retrieval_provider,
            "retrieval_model": self.retrieval_model,
            "sections_count": self.sections_count,
            "sources_count": self.sources_count,
            "report_path": self.report_path,
            "preview": self.report_markdown_preview,
            "warnings": self.warnings,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def record_analysis_run(
    session: Session,
    *,
    registry_number: str,
    status: str,
    used_llm: bool = False,
    llm_model: str | None = None,
    retrieval_provider: str | None = None,
    retrieval_model: str | None = None,
    sections_count: int = 0,
    sources_count: int = 0,
    report_path: str | None = None,
    report_markdown: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    duration_seconds: float | None = None,
    source: str | None = None,
    metadata: dict | None = None,
) -> TenderAnalysisRun:
    now = datetime.now(UTC)
    preview = _generate_preview(report_markdown) if report_markdown else None
    source_value = str(source).strip() if source is not None else None
    metadata_value = dict(metadata or {})
    if source_value and len(source_value) > _SOURCE_MAX_LENGTH:
        metadata_value.setdefault("history_source_full", source_value)
        source_value = source_value[:_SOURCE_MAX_LENGTH]
    run = TenderAnalysisRun(
        registry_number=registry_number,
        status=status,
        used_llm=used_llm,
        llm_model=llm_model,
        retrieval_provider=retrieval_provider,
        retrieval_model=retrieval_model,
        sections_count=sections_count,
        sources_count=sources_count,
        report_path=report_path,
        report_markdown_preview=preview,
        warnings_json=json.dumps(warnings, ensure_ascii=False) if warnings else None,
        errors_json=json.dumps(errors, ensure_ascii=False) if errors else None,
        duration_seconds=duration_seconds,
        source=source_value,
        metadata_json=(
            json.dumps(metadata_value, ensure_ascii=False)
            if metadata_value
            else None
        ),
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.commit()
    return run


def list_analysis_runs(
    session: Session,
    *,
    registry_number: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[AnalysisRunRecord]:
    query = session.query(TenderAnalysisRun)
    if registry_number:
        query = query.filter(TenderAnalysisRun.registry_number == registry_number)
    if status:
        query = query.filter(TenderAnalysisRun.status == status)
    query = query.order_by(desc(TenderAnalysisRun.created_at)).offset(offset).limit(limit)
    runs = query.all()
    total = _count_runs(session, registry_number=registry_number, status=status)
    return [AnalysisRunRecord(r) for r in runs], total


def _count_runs(
    session: Session,
    *,
    registry_number: str | None = None,
    status: str | None = None,
) -> int:
    query = session.query(TenderAnalysisRun)
    if registry_number:
        query = query.filter(TenderAnalysisRun.registry_number == registry_number)
    if status:
        query = query.filter(TenderAnalysisRun.status == status)
    return query.count()


def get_analysis_run(session: Session, run_id: str) -> AnalysisRunRecord | None:
    run = session.query(TenderAnalysisRun).filter(TenderAnalysisRun.id == run_id).first()
    if run is None:
        return None
    return AnalysisRunRecord(run)


def get_analysis_run_report(session: Session, run_id: str, data_dir: str) -> tuple[AnalysisRunRecord | None, str | None, str | None]:
    record = get_analysis_run(session, run_id)
    if record is None:
        return None, None, "Run not found"
    resolved = _resolve_report_path(record.report_path, data_dir)
    if resolved is None:
        if record.report_path:
            return record, None, "Report file is missing or inaccessible"
        return record, None, "No report file was saved for this run"
    try:
        markdown = Path(resolved).read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return record, None, f"Failed to read report file: {e}"
    return record, markdown, None


def get_latest_analysis_run(session: Session, registry_number: str) -> AnalysisRunRecord | None:
    run = (
        session.query(TenderAnalysisRun)
        .filter(TenderAnalysisRun.registry_number == registry_number)
        .order_by(desc(TenderAnalysisRun.created_at))
        .first()
    )
    if run is None:
        return None
    return AnalysisRunRecord(run)


def get_latest_analysis_report(session: Session, registry_number: str, data_dir: str) -> tuple[AnalysisRunRecord | None, str | None, str | None]:
    record = get_latest_analysis_run(session, registry_number)
    if record is None:
        return None, None, "No analysis runs found for this registry number"
    resolved = _resolve_report_path(record.report_path, data_dir)
    if resolved is None:
        if record.report_path:
            return record, None, "Report file is missing or inaccessible"
        return record, None, "No report file was saved for this run"
    try:
        markdown = Path(resolved).read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return record, None, f"Failed to read report file: {e}"
    return record, markdown, None
