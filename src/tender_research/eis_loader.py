from __future__ import annotations

from datetime import datetime
from typing import Any

from src.tender_research.errors import EisLoaderError
from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw


class EisTenderLoader:
    def __init__(self, mode: str = "demo", discovery_mode: str = "registry_numbers", real_loader=None):
        self._mode = mode
        self._discovery_mode = discovery_mode
        self._real = real_loader

    @property
    def _real_loader(self):
        if self._real is None:
            from src.tender_research.eis_real_loader import RealEisLoader
            self._real = RealEisLoader()
        return self._real

    def fetch_tenders(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int | None = None,
        law_type: str | None = None,
        query: str | None = None,
    ) -> list[EisTenderRaw]:
        if self._mode == "real":
            if self._discovery_mode == "search":
                return self._real_loader.fetch_tenders(date_from, date_to, limit, law_type, query)
            raise EisLoaderError(
                "fetch_tenders() is unavailable in real registry-number mode; "
                "use fetch_by_registry_number(s) or switch discovery_mode=search"
            )
        return _get_demo_tenders(date_from, date_to, limit, law_type, query)

    def fetch_tender_details(self, external_id: str) -> EisTenderRaw | None:
        if self._mode == "real":
            try:
                return self._real_loader.fetch_tender_details(external_id)
            except Exception:
                return None
        for t in _get_demo_tenders():
            if t.external_id == external_id:
                return t
        return None

    def fetch_tender_documents(self, tender: EisTenderRaw) -> list[EisDocumentRaw]:
        if self._mode == "real":
            try:
                return self._real_loader.fetch_tender_documents(tender)
            except Exception:
                return []
        return _get_demo_documents(tender.external_id)

    def fetch_by_registry_number(self, registry_number: str) -> EisTenderRaw | None:
        if self._mode != "real":
            for t in _get_demo_tenders():
                if t.registry_number == registry_number:
                    return t
            return None
        return self._real_loader.fetch_by_registry_number(registry_number)


# ── Demo / fallback data for smoke testing ──

_DEMO_TENDERS: list[dict[str, Any]] = [
    {
        "external_id": "0373100000124000001",
        "title": "Поставка компьютерного оборудования для нужд школы № 42",
        "customer_name": "ГБОУ Школа № 42",
        "customer_inn": "7712345678",
        "customer_kpp": "771601001",
        "region": "Москва",
        "law_type": "44fz",
        "nmck_amount": 5000000.0,
        "currency": "RUB",
        "publication_date": datetime(2026, 7, 1, 12, 0, 0),
        "application_deadline": datetime(2026, 8, 1, 10, 0, 0),
        "status": "active",
        "registry_number": "0373100000124000001",
        "eis_url": "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=0373100000124000001",
    },
    {
        "external_id": "0373100000124000002",
        "title": "Оказание услуг по уборке помещений",
        "customer_name": "ФГБУ Поликлиника № 15",
        "customer_inn": "7798765432",
        "customer_kpp": "771601001",
        "region": "Москва",
        "law_type": "44fz",
        "nmck_amount": 1200000.0,
        "currency": "RUB",
        "publication_date": datetime(2026, 7, 2, 9, 0, 0),
        "application_deadline": datetime(2026, 8, 5, 10, 0, 0),
        "status": "active",
        "registry_number": "0373100000124000002",
    },
    {
        "external_id": "0373100000124000003",
        "title": "Поставка медицинского оборудования (аппараты УЗИ)",
        "customer_name": "ГБУЗ Городская больница № 7",
        "customer_inn": "7755112233",
        "customer_kpp": "771601001",
        "region": "Санкт-Петербург",
        "law_type": "44fz",
        "nmck_amount": 8500000.0,
        "currency": "RUB",
        "publication_date": datetime(2026, 7, 3, 14, 0, 0),
        "application_deadline": datetime(2026, 8, 10, 10, 0, 0),
        "status": "active",
        "registry_number": "0373100000124000003",
    },
]


def _get_demo_tenders(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int | None = None,
    law_type: str | None = None,
    query: str | None = None,
) -> list[EisTenderRaw]:
    def _strip_tz(dt: datetime | None) -> datetime | None:
        if dt is not None and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    date_from_naive = _strip_tz(date_from)
    date_to_naive = _strip_tz(date_to)

    results = []
    for item in _DEMO_TENDERS:
        pub = item.get("publication_date")
        if date_from_naive and pub and pub < date_from_naive:
            continue
        if date_to_naive and pub and pub > date_to_naive:
            continue
        if law_type and item.get("law_type") != law_type:
            continue
        if query and query.lower() not in (item.get("title", "") + (item.get("customer_name") or "")).lower():
            continue
        results.append(EisTenderRaw(**item, is_demo=True))
    if limit:
        results = results[:limit]
    return results


_DEMO_DOCUMENTS: dict[str, list[dict[str, Any]]] = {
    "0373100000124000001": [
        {
            "file_name": "contract_draft.docx",
            "file_url": None,
            "source_document_id": "doc-001",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        {
            "file_name": "technical_spec.pdf",
            "file_url": None,
            "source_document_id": "doc-002",
            "content_type": "application/pdf",
        },
    ],
}


def _get_demo_documents(external_id: str) -> list[EisDocumentRaw]:
    docs = _DEMO_DOCUMENTS.get(external_id, [])
    return [EisDocumentRaw(**d) for d in docs]
