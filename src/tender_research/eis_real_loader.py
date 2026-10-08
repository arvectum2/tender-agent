from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementSearchRequest,
)
from src.modules.tender_operator_agent_demo.settings import (
    get_zakupki_soap_settings,
)
from src.modules.tender_operator_agent_demo.zakupki_soap_client import (
    ZakupkiSoapClient,
)
from src.tender_research.errors import (
    EisAuthFailedError,
    EisConnectionResetError,
    EisLoaderError,
    EisMissingTokenError,
    EisNoDataError,
    classify_eis_error,
)
from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw

logger = logging.getLogger(__name__)


class RealEisLoader:
    def __init__(self, soap_client: ZakupkiSoapClient | None = None):
        self._client = soap_client or self._build_client()

    @staticmethod
    def _build_client() -> ZakupkiSoapClient:
        settings = get_zakupki_soap_settings()
        if not settings.configured:
            logger.warning(
                "ZakupkiSoapSettings not configured (token missing or disabled). "
                "EIS SOAP calls will fail."
            )
        return ZakupkiSoapClient(settings)

    # ── Configuration check (for CLI) ──

    def check_config(self) -> dict[str, Any]:
        settings = get_zakupki_soap_settings()
        token = settings.token or ""
        masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****"
        methods = []
        client_configured = self._client.is_configured()
        if client_configured:
            if self._probe_legacy():
                methods.append("searchProcurements (legacy)")
            if self._probe_getdocs():
                methods.append("getDocsByReestrNumber")
        return {
            "eis_mode": "real",
            "endpoint": settings.individual_base_url,
            "legacy_endpoint": settings.base_url,
            "token_present": bool(token) and client_configured,
            "token_masked": masked,
            "token_owner": settings.token_owner,
            "ssl_verify": False,
            "configured": client_configured,
            "available_methods": methods or ["(none confirmed)"],
        }

    def _probe_legacy(self) -> bool:
        try:
            from src.modules.tender_operator_agent_demo.procurement_schemas import (
                ProcurementSearchRequest,
            )
            self._client.search_procurements(
                ProcurementSearchRequest(query="тест", max_results=1)
            )
            return True
        except EisConnectionResetError:
            return False
        except Exception:
            return False

    def _probe_getdocs(self) -> bool:
        try:
            result = self._client.get_docs_by_reestr_number("0000000000000000")
            return result.status in ("no_data", "completed")
        except EisConnectionResetError:
            return False
        except Exception:
            return False

    # ── Public API (matches EisTenderLoader interface) ──

    def fetch_tenders(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int | None = None,
        law_type: str | None = None,
        query: str | None = None,
    ) -> list[EisTenderRaw]:
        raw_results = self._search_procurements(
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            law_type=law_type,
            query=query,
        )
        tenders: list[EisTenderRaw] = []
        for r in raw_results:
            try:
                tenders.append(self._result_to_raw(r))
            except Exception as e:
                logger.error("Failed to normalize search result %s: %s", r.procurement_id, e)
        return tenders

    def fetch_tender_details(self, external_id: str) -> EisTenderRaw | None:
        if not self._client.is_configured():
            logger.warning("EIS SOAP not configured, cannot fetch details for %s", external_id)
            return None
        try:
            details = self._client.get_procurement_details(external_id)
            raw = self._result_to_raw(details.procurement)
            docs = self._attachments_to_raw(details.attachments)
            raw.documents = docs
            return raw
        except EisConnectionResetError:
            logger.warning("Legacy endpoint connection reset for details %s", external_id)
            return None
        except Exception as e:
            logger.error("Failed to fetch details for %s: %s", external_id, e)
            return None

    def fetch_tender_documents(self, tender: EisTenderRaw) -> list[EisDocumentRaw]:
        if tender.law_type == "223fz":
            return tender.documents or []  # Never use 44-FZ legacy listAttachments.
        if not self._client.is_configured():
            return []
        try:
            attachments = self._client.list_attachments(tender.external_id)
            return self._attachments_to_raw(attachments)
        except EisConnectionResetError:
            logger.warning("Legacy endpoint connection reset for documents %s", tender.external_id)
            return []
        except Exception as e:
            logger.error("Failed to fetch documents for %s: %s", tender.external_id, e)
            return []

    # ── Registry number based fetch (getDocsIP path) ──

    def fetch_by_registry_number(self, registry_number: str, *, law_type: str | None = None) -> EisTenderRaw | None:
        if law_type not in (None, "44fz", "223fz"):
            raise EisLoaderError("unsupported procurement regime")
        if law_type == "223fz":
            return self._fetch_ri223_by_registry_number(registry_number)
        if not self._client.is_configured():
            raise EisMissingTokenError("EIS SOAP not configured")
        try:
            result = self._client.get_docs_by_reestr_number(registry_number)
        except EisConnectionResetError as e:
            raise EisConnectionResetError(
                f"getDocsIP connection reset for {registry_number}: {e}"
            ) from e
        except Exception as e:
            raise classify_eis_error(e) from e

        if result.status == "soap_fault":
            raise EisAuthFailedError(
                f"SOAP fault for {registry_number}: {result.warnings}"
            )
        if result.status in ("validation_error", "processing_error"):
            raise EisLoaderError(
                f"getDocsIP error for {registry_number}: {result.status} — {result.warnings}"
            )
        if result.status == "no_data":
            raise EisNoDataError(
                f"No documents found for registry number {registry_number}"
            )
        if result.status == "no_archive_url":
            raise EisNoDataError(
                f"No archive URL for {registry_number}"
            )
        return EisTenderRaw(
            external_id=registry_number,
            registry_number=registry_number,
            title=f"Закупка {registry_number}",
            status="completed",
            raw_payload={
                "get_docs_ip_status": result.status,
                "archive_url": result.archive_url,
                "archive_urls": result.archive_urls,
                "warnings": result.warnings,
            },
        )

    def _fetch_ri223_by_registry_number(self, registry_number: str) -> EisTenderRaw:
        """Explicit opt-in only; never infer 223-FZ regime from registry number."""
        from src.tender_research.providers.ri223_soap_evidence import (
            Ri223EvidenceError,
            parse_ri223_archive,
        )

        if not self._client.is_configured():
            raise EisMissingTokenError("EIS SOAP not configured")
        try:
            result = self._client.get_docs_by_reestr_number(
                registry_number, subsystem_type="RI223",
            )
        except Exception as exc:
            raise classify_eis_error(exc) from exc
        if result.status == "no_data":
            raise EisNoDataError(f"No RI223 documents for {registry_number}")
        if result.status != "completed":
            raise EisLoaderError(f"RI223 transport not complete: {result.status}")
        urls = list(dict.fromkeys(
            url for url in [result.archive_url, *result.archive_urls] if url
        ))
        if len(urls) != 1:
            raise EisLoaderError("RI223 archive URL is missing or ambiguous")
        try:
            with TemporaryDirectory(prefix="ri223-getdocs-") as temporary:
                target = Path(temporary)
                download = self._client.download_archive(urls[0], target)
                return parse_ri223_archive(target / download.stored_name, registry_number)
        except Ri223EvidenceError as exc:
            raise EisLoaderError(f"RI223 source evidence unsupported: {exc}") from exc

    # ── Internal helpers ──

    def _search_procurements(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int | None = None,
        law_type: str | None = None,
        query: str | None = None,
    ) -> list:
        if not self._client.is_configured():
            logger.warning("EIS SOAP not configured, returning empty search results")
            return []
        req = ProcurementSearchRequest(
            source="zakupki_gov_ru_soap_legacy",
            query=query or "",
            law=law_type,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
            max_results=limit or 20,
        )
        try:
            return self._client.search_procurements(req)
        except EisConnectionResetError as e:
            raise
        except Exception as e:
            logger.error("EIS SOAP search failed: %s", e)
            return []

    def _result_to_raw(self, r) -> EisTenderRaw:
        try:
            pub_date = self._parse_dt(r.publication_date)
            deadline = self._parse_dt(r.deadline)
        except Exception:
            pub_date = None
            deadline = None

        nmck = r.initial_price
        if nmck is not None:
            nmck = float(nmck)

        return EisTenderRaw(
            external_id=r.procurement_id,
            title=r.title,
            customer_name=r.customer_name,
            customer_inn=r.customer_inn,
            law_type=r.law,
            nmck_amount=nmck,
            currency=r.currency or "RUB",
            publication_date=pub_date,
            application_deadline=deadline,
            status=r.status,
            registry_number=r.registry_number,
            purchase_number=r.notice_number,
            eis_url=r.source_url,
            raw_payload=r.model_dump(mode="json") if hasattr(r, "model_dump") else None,
        )

    def _attachments_to_raw(self, attachments: list) -> list[EisDocumentRaw]:
        return [
            EisDocumentRaw(
                file_name=a.name,
                file_url=a.url,
                source_document_id=a.attachment_id,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
            )
            for a in attachments
            if a.name
        ]

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d.%m.%Y %H:%M",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            from datetime import timezone
            return datetime.fromisoformat(value)
        except Exception:
            return None
