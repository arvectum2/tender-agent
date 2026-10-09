"""APR-03B: bounded private operator data projection; no second procurement engine."""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.modules.tender_operator_agent_demo.procurement_intake_service import (
    create_run_from_search_result,
)
from src.modules.tender_operator_agent_demo.schemas import (
    SearchResultHandoffRequest,
    SearchResultHandoffResponse,
)
from src.shared.config.settings import get_settings
from src.tender_research.models import ProcurementTender, ProcurementTenderDocument

_NUMBER_44 = re.compile(r"\d{19}\Z")
_NUMBER_223 = re.compile(r"\d{11}\Z")
_VALID_ID = re.compile(r"[a-zA-Z0-9-]{1,36}\Z")
_MAX_DOWNLOAD = 30 * 1024 * 1024


def parse_eis_reference(reference: str) -> tuple[str, str, str | None]:
    """Strict origin/path check: supplied URLs never become arbitrary network targets."""
    raw = reference.strip()
    supplied_url = None
    if _NUMBER_44.fullmatch(raw):
        number, law = raw, "44fz"
    elif _NUMBER_223.fullmatch(raw):
        number, law = raw, "223fz"
    else:
        parts = urlsplit(raw)
        if (
            parts.scheme != "https"
            or parts.hostname not in {"zakupki.gov.ru", "www.zakupki.gov.ru"}
            or parts.username or parts.password or parts.netloc.lower() not in {"zakupki.gov.ru", "www.zakupki.gov.ru"}
            or parts.fragment
        ):
            raise ValueError("Укажите реестровый номер или HTTPS-ссылку на zakupki.gov.ru")
        if parts.path.startswith("/epz/order/notice/"):
            law = "44fz"
        elif parts.path.startswith("/223/purchase/public/purchase/info/"):
            law = "223fz"
        else:
            raise ValueError("Ссылка должна вести на официальное извещение 44-ФЗ или 223-ФЗ")
        numbers = parse_qs(parts.query).get("regNumber", [])
        if len(numbers) != 1:
            raise ValueError("В ссылке требуется единственный regNumber")
        number = numbers[0]
        supplied_url = raw
    if not (_NUMBER_44.fullmatch(number) if law == "44fz" else _NUMBER_223.fullmatch(number)):
        raise ValueError("Неверная длина реестрового номера для выбранного закона")
    url = supplied_url
    if not url and law == "223fz":
        url = "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=" + number
    return number, law, url


def import_eis_reference(reference: str) -> SearchResultHandoffResponse:
    number, law, url = parse_eis_reference(reference)
    return create_run_from_search_result(
        SearchResultHandoffRequest(
            reestr_number=number,
            law=law,
            source="public_eis_html_223fz" if law == "223fz" else "public_eis_html_44fz",
            source_url=url,
            download_archive=True,
            analyze_after_download=False,
        )
    )


@contextmanager
def read_session():
    # Uses the existing canonical database, never creates tables or runs migrations.
    from sqlalchemy import create_engine

    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine, autoflush=False) as session:
            yield session
            session.rollback()
    finally:
        engine.dispose()


def registry_records(*, query: str = "", limit: int = 25, offset: int = 0) -> dict:
    if not 1 <= limit <= 50 or offset < 0 or len(query) > 128:
        raise ValueError("Неверные параметры просмотра базы")
    with read_session() as session:
        records = session.query(ProcurementTender)
        if query.strip():
            backslash = chr(92)
            escaped = query.strip().replace(backslash, backslash * 2).replace("%", backslash + "%").replace("_", backslash + "_")
            term = f"%{escaped}%"
            records = records.filter(
                or_(
                    ProcurementTender.registry_number.ilike(term, escape="\\"),
                    ProcurementTender.title.ilike(term, escape="\\"),
                    ProcurementTender.customer_name.ilike(term, escape="\\"),
                )
            )
        count = records.with_entities(func.count(ProcurementTender.id)).scalar() or 0
        page = records.order_by(ProcurementTender.updated_at.desc(), ProcurementTender.id).offset(offset).limit(limit).all()
        return {
            "total": count,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": record.id,
                    "registry_number": record.registry_number,
                    "law": record.law_type,
                    "title": record.title,
                    "customer_name": record.customer_name,
                    "nmck_amount": record.nmck_amount,
                    "currency": record.currency,
                    "status": record.status,
                    "eis_url": record.eis_url if _safe_eis_link(record.eis_url) else None,
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                }
                for record in page
            ],
        }


def _safe_eis_link(url: str | None) -> bool:
    if not url:
        return False
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in {"zakupki.gov.ru", "www.zakupki.gov.ru"} and not parts.username and not parts.password and parts.port is None


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Запись не найдена") from exc


def registry_detail(tender_id: str) -> dict:
    key = _uuid(tender_id)
    with read_session() as session:
        record = session.get(ProcurementTender, key)
        if record is None:
            raise HTTPException(status_code=404, detail="Закупка не найдена")
        docs = (
            session.query(ProcurementTenderDocument)
            .filter(ProcurementTenderDocument.tender_id == key)
            .order_by(ProcurementTenderDocument.created_at.desc())
            .limit(200)
            .all()
        )
        return {
            "id": record.id,
            "registry_number": record.registry_number,
            "law": record.law_type,
            "title": record.title,
            "customer_name": record.customer_name,
            "nmck_amount": record.nmck_amount,
            "currency": record.currency,
            "status": record.status,
            "eis_url": record.eis_url if _safe_eis_link(record.eis_url) else None,
            "documents": [
                {
                    "id": doc.id,
                    "name": doc.file_name,
                    "download_status": doc.download_status,
                    "text_extraction_status": doc.text_extraction_status,
                    "size_bytes": doc.size_bytes,
                    "sha256": doc.sha256,
                    "local_download": _allowed_document_path(doc.local_path) is not None,
                }
                for doc in docs
            ],
        }


def _allowed_document_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    root = Path(get_settings().arvectum_data_dir).resolve()
    candidate = Path(raw_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    if candidate.stat().st_size > _MAX_DOWNLOAD:
        return None
    return candidate


def original_document(tender_id: str, document_id: str) -> FileResponse:
    key, document_key = _uuid(tender_id), _uuid(document_id)
    with read_session() as session:
        doc = (
            session.query(ProcurementTenderDocument)
            .filter(ProcurementTenderDocument.id == document_key, ProcurementTenderDocument.tender_id == key)
            .first()
        )
        if doc is None:
            raise HTTPException(status_code=404, detail="Документ не найден")
        path = _allowed_document_path(doc.local_path)
        if path is None:
            raise HTTPException(status_code=404, detail="Локальная копия документа недоступна")
        return FileResponse(path, filename=Path(doc.file_name).name, media_type="application/octet-stream")
