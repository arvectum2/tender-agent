from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.tender_research.browser.fetcher import WebPageFetcher
from src.tender_research.browser.requests_fetcher import RequestsFetcher
from src.tender_research.config import TenderResearchConfig, load_config
from src.tender_research.dedupe import content_hash, normalize_url, url_hash
from src.tender_research.document_store import download_tender_documents
from src.tender_research.eis_loader import EisTenderLoader
from src.tender_research.errors import (
    EisConnectionResetError,
    EisMissingTokenError,
    EisNoDataError,
    classify_eis_error,
)
from src.tender_research.ingest_checkpoint import IngestCheckpointStore
from src.tender_research.providers.public_223fz_search import Public223FzSearchProvider
from src.tender_research.providers.public_44fz_search import (
    Public44FzSearchProvider,
    PublicTenderDetail,
)
from src.tender_research.providers.duckduckgo_html import DuckDuckGoHtmlSearchProvider
from src.tender_research.providers.manual_urls import ManualUrlsSearchProvider
from src.tender_research.query_builder import build_search_queries
from src.tender_research.rate_limit import RateLimiter
from src.tender_research.registry_discovery import (
    DiscoveredRegistryNumber,
    DiscoveryResult,
    RegistryNumberDiscovery,
    SourceType,
)
from src.tender_research.repository import TenderRepository
from src.tender_research.search_provider import SearchProvider
from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw, TenderUpsertData

logger = logging.getLogger(__name__)


class TenderResearchPipeline:
    def __init__(
        self,
        session: Session,
        config: TenderResearchConfig | None = None,
        eis_loader: EisTenderLoader | None = None,
        search_provider: SearchProvider | None = None,
        web_fetcher: WebPageFetcher | None = None,
    ):
        self._session = session
        self._config = config or load_config()
        self._repo = TenderRepository(session)
        self._eis = eis_loader or EisTenderLoader(mode=self._config.eis_mode, discovery_mode=self._config.eis_discovery_mode)
        self._search_provider = search_provider or DuckDuckGoHtmlSearchProvider(
            timeout=int(self._config.web_search_timeout_seconds),
        )
        self._web_fetcher = web_fetcher or RequestsFetcher()
        self._search_limiter = RateLimiter(delay_seconds=self._config.web_search_delay_seconds)
        self._fetch_limiter = RateLimiter(delay_seconds=self._config.web_fetch_delay_seconds)
        self._public_provider = Public44FzSearchProvider(
            timeout_seconds=self._config.public_search_timeout_seconds,
            delay_seconds=self._config.public_search_delay_seconds,
            bypass_proxy=self._config.public_search_bypass_proxy,
            no_proxy_domains=self._config.public_search_no_proxy_domains,
        )
        self._public_223fz_provider = Public223FzSearchProvider(
            timeout_seconds=self._config.public_search_timeout_seconds,
            delay_seconds=self._config.public_search_delay_seconds,
            bypass_proxy=self._config.public_search_bypass_proxy,
            no_proxy_domains=self._config.public_search_no_proxy_domains,
        )
        self._last_discovered_batch_summary: dict[str, Any] | None = None

    # ── Step 1: Ingest tenders from EIS ──

    def ingest_eis_tenders(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int | None = None,
        law_type: str | None = None,
        query: str | None = None,
    ) -> int:
        batch_limit = limit or self._config.batch_limit
        raw_tenders = self._eis.fetch_tenders(
            date_from=date_from,
            date_to=date_to,
            limit=batch_limit,
            law_type=law_type,
            query=query,
        )
        saved = 0
        for raw in raw_tenders:
            try:
                saved += self._save_one_tender(raw)
            except Exception as e:
                logger.error("Failed to ingest tender %s: %s", raw.external_id, e)
        self._session.commit()
        return saved

    def ingest_eis_by_registry_numbers(
        self,
        registry_numbers: list[str],
        limit: int | None = None,
        *,
        checkpoint_key: str | None = None,
        resume: bool = True,
    ) -> dict[str, Any]:
        numbers = registry_numbers[:limit] if limit else registry_numbers
        result: dict[str, Any] = {
            "total": len(numbers),
            "saved": 0,
            "skipped": 0,
            "errors": [],
            "connection_resets": 0,
            "no_data": 0,
            "missing_token": False,
        }
        checkpoint_store = None
        checkpoint = None
        start_index = 0
        if checkpoint_key:
            checkpoint_store = IngestCheckpointStore(self._config.data_dir)
            checkpoint = checkpoint_store.begin(
                key=checkpoint_key,
                source="eis_registry_numbers",
                items=numbers,
                resume=resume,
            )
            start_index = checkpoint.next_index
            result["checkpoint_key"] = checkpoint_key
            result["resumed_from_index"] = start_index
            result["checkpoint_status"] = checkpoint.status

        for index in range(start_index, len(numbers)):
            rn = numbers[index]
            try:
                raw = self._eis.fetch_by_registry_number(rn)
                if raw is None:
                    result["skipped"] += 1
                    if checkpoint_store and checkpoint:
                        checkpoint = checkpoint_store.advance(
                            checkpoint, next_index=index + 1, external_id=rn
                        )
                    continue
                self._save_one_tender(raw)
                if checkpoint_store:
                    # Commit source state before advancing the durable cursor. A crash
                    # between these operations only replays an idempotent upsert.
                    self._session.commit()
                result["saved"] += 1
                if checkpoint_store and checkpoint:
                    checkpoint = checkpoint_store.advance(
                        checkpoint, next_index=index + 1, external_id=rn
                    )
            except EisMissingTokenError:
                self._session.rollback()
                result["missing_token"] = True
                result["errors"].append(f"{rn}: token missing")
                if checkpoint_store and checkpoint:
                    checkpoint = checkpoint_store.fail(
                        checkpoint, external_id=rn, error="missing_token"
                    )
                break
            except EisConnectionResetError:
                self._session.rollback()
                result["connection_resets"] += 1
                result["errors"].append(f"{rn}: connection reset")
                if checkpoint_store and checkpoint:
                    checkpoint = checkpoint_store.fail(
                        checkpoint, external_id=rn, error="connection_reset"
                    )
                    break
            except EisNoDataError:
                self._session.rollback()
                result["no_data"] += 1
                if checkpoint_store and checkpoint:
                    checkpoint = checkpoint_store.advance(
                        checkpoint, next_index=index + 1, external_id=rn
                    )
            except Exception as e:  # noqa: BLE001 - preserve legacy batch error capture
                self._session.rollback()
                result["errors"].append(f"{rn}: {e}")
                if checkpoint_store and checkpoint:
                    checkpoint = checkpoint_store.fail(
                        checkpoint, external_id=rn, error=f"{type(e).__name__}: {e}"
                    )
                    break

        if not checkpoint_store:
            self._session.commit()
        elif checkpoint is not None:
            result["checkpoint_status"] = checkpoint.status
            result["next_index"] = checkpoint.next_index
        return result

    def _save_one_tender(self, raw: EisTenderRaw) -> int:
        upsert_data = self._normalize_tender(raw)
        tender = self._repo.upsert_tender(upsert_data.tender)
        if upsert_data.customer:
            self._repo.upsert_customer(upsert_data.customer)
        for doc_data in upsert_data.documents:
            doc_data["tender_id"] = tender.id
            self._repo.upsert_document(doc_data)
        self._save_raw_payload(tender, raw)
        return 1

    # ── Discovery ──

    def discover_registry_numbers(
        self,
        source: str = "auto",
        days_back: int | None = None,
        limit: int | None = None,
        seed_file: str | None = None,
        page_size: int | None = None,
    ) -> DiscoveryResult:
        discovery = RegistryNumberDiscovery(
            config=self._config,
            eis_loader=self._eis,
        )
        result = discovery.discover(
            source=source,
            days_back=days_back,
            limit=limit,
            seed_file=seed_file,
            page_size=page_size or self._config.public_search_page_size,
        )
        logger.info(
            "Discovered %d registry numbers from source=%s (is_demo=%s)",
            len(result.numbers), result.selected_source, result.is_demo,
        )
        return result

    def run_discovered_batch(
        self,
        source: str = "auto",
        days_back: int | None = None,
        limit: int | None = None,
        seed_file: str | None = None,
        page_size: int | None = None,
    ) -> list[dict[str, int | str]]:
        disc_result = self.discover_registry_numbers(
            source=source,
            days_back=days_back,
            limit=limit,
            seed_file=seed_file,
            page_size=page_size,
        )
        if not disc_result.numbers:
            logger.warning("No registry numbers discovered, nothing to do")
            self._last_discovered_batch_summary = self._build_discovered_batch_summary(disc_result)
            return []

        results: list[dict[str, int | str]] = []
        summary = self._build_discovered_batch_summary(disc_result)
        for discovered in disc_result.numbers:
            summary["ingest_attempts"] += 1
            try:
                tender, tender_summary = self._ingest_discovered_tender(discovered)
                for key, value in tender_summary.items():
                    if isinstance(value, int):
                        summary[key] = summary.get(key, 0) + value
                self._session.commit()
                run_result = self.run_full(tender.id)
                summary["documents_downloaded"] += int(run_result.get("documents_downloaded", 0) or 0)
                summary["failed_document_downloads"] += int(run_result.get("documents_failed", 0) or 0)
                run_result["registry_number"] = discovered.registry_number
                run_result["title"] = tender.title
                results.append(run_result)
            except Exception as exc:
                self._session.rollback()
                logger.exception("Failed to ingest discovered tender %s", discovered.registry_number)
                summary["errors"].append(f"{discovered.registry_number}: {exc}")
                results.append({
                    "registry_number": discovered.registry_number,
                    "error": str(exc),
                })

        self._last_discovered_batch_summary = summary
        summary["extracted_texts_total"] = self._repo.count_documents_by_text_status("extracted")
        summary["unsupported_documents"] = self._repo.count_documents_by_text_status("unsupported")
        summary["empty_text_documents"] = self._repo.count_documents_by_text_status("empty")

        return results

    @property
    def last_discovered_batch_summary(self) -> dict[str, Any] | None:
        return self._last_discovered_batch_summary

    def _build_discovered_batch_summary(self, disc_result: DiscoveryResult) -> dict[str, Any]:
        return {
            "requested_limit": disc_result.requested_limit,
            "effective_limit": disc_result.effective_limit,
            "requested_page_size": disc_result.requested_page_size,
            "effective_page_size": disc_result.effective_page_size,
            "date_from": disc_result.date_from.isoformat() if disc_result.date_from else None,
            "date_to": disc_result.date_to.isoformat() if disc_result.date_to else None,
            "source_url": disc_result.source_url,
            "discovered_count": disc_result.discovered_count or len(disc_result.numbers),
            "selected_source": disc_result.selected_source,
            "pages_read": disc_result.pages_read,
            "items_raw_count": disc_result.items_raw_count,
            "items_with_registry_number": disc_result.items_with_registry_number,
            "items_skipped_without_registry_number": disc_result.skipped_without_registry_number,
            "items_after_dedupe": disc_result.items_after_dedupe,
            "items_after_demo_filter": disc_result.items_after_demo_filter,
            "tenders_created": 0,
            "tenders_updated": 0,
            "tenders_with_title": 0,
            "tenders_with_customer": 0,
            "tenders_with_publication_date": 0,
            "tenders_with_nmck": 0,
            "placeholder_title_count": 0,
            "customers_created": 0,
            "public_detail_fetched": 0,
            "public_detail_failed": 0,
            "detail_fetch_attempts": 0,
            "detail_fetch_success": 0,
            "ingest_attempts": 0,
            "public_document_links_found": 0,
            "documents_created_from_public_links": 0,
            "documents_downloaded": 0,
            "extracted_texts_total": 0,
            "unsupported_documents": 0,
            "empty_text_documents": 0,
            "failed_document_downloads": 0,
            "errors": [],
        }

    def _ingest_discovered_tender(
        self,
        discovered: DiscoveredRegistryNumber,
    ) -> tuple[Any, dict[str, int]]:
        summary = {
            "tenders_created": 0,
            "tenders_updated": 0,
            "tenders_with_title": 0,
            "tenders_with_customer": 0,
            "tenders_with_publication_date": 0,
            "tenders_with_nmck": 0,
            "placeholder_title_count": 0,
            "customers_created": 0,
            "public_detail_fetched": 0,
            "public_detail_failed": 0,
            "detail_fetch_attempts": 1,
            "detail_fetch_success": 0,
            "public_document_links_found": 0,
            "documents_created_from_public_links": 0,
        }
        existing_tender = self._repo.get_tender_by_external("eis", discovered.registry_number)
        detail_provider = (
            self._public_223fz_provider
            if discovered.source_type == SourceType.EXTERNAL_PUBLIC_223FZ or discovered.law_type == "223fz"
            else self._public_provider
        )
        detail = detail_provider.fetch_detail(discovered.card_url, registry_number=discovered.registry_number)
        if detail.network_status == "success":
            summary["public_detail_fetched"] += 1
            summary["detail_fetch_success"] += 1
        else:
            summary["public_detail_failed"] += 1

        soap_raw, soap_status = self._fetch_eis_by_registry_number_safe(discovered.registry_number)
        if detail.document_links:
            summary["public_document_links_found"] += len(detail.document_links)

        upsert_data = self._build_upsert_from_discovery(discovered, detail, soap_raw, soap_status, existing_tender=existing_tender)
        tender = self._repo.upsert_tender(upsert_data.tender)
        summary["tenders_created" if existing_tender is None else "tenders_updated"] += 1
        if upsert_data.customer:
            before_customers = self._repo.count_customers()
            self._repo.upsert_customer(upsert_data.customer)
            if self._repo.count_customers() > before_customers:
                summary["customers_created"] += 1
        before_docs = self._repo.count_documents()
        for doc_data in upsert_data.documents:
            doc_data["tender_id"] = tender.id
            self._repo.upsert_document(doc_data)
        summary["documents_created_from_public_links"] += max(0, self._repo.count_documents() - before_docs)

        if soap_raw:
            self._save_raw_payload(tender, soap_raw)
        self._save_public_detail_artifacts(tender, detail)

        if tender.title:
            summary["tenders_with_title"] += 1
            if _is_placeholder_title(tender.title, discovered.registry_number):
                summary["placeholder_title_count"] += 1
        if tender.customer_name:
            summary["tenders_with_customer"] += 1
        if tender.publication_date:
            summary["tenders_with_publication_date"] += 1
        if tender.nmck_amount is not None:
            summary["tenders_with_nmck"] += 1

        return tender, summary

    def backfill_public_metadata(
        self,
        limit: int = 50,
        only_placeholders: bool = True,
        days_back: int | None = None,
        with_documents: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        candidates = self._repo.list_placeholder_tenders(
            limit=limit,
            only_placeholders=only_placeholders,
            days_back=days_back,
        )
        summary: dict[str, Any] = {
            "placeholders_found": len(candidates),
            "processed": 0,
            "enriched_title_count": 0,
            "enriched_customer_count": 0,
            "enriched_publication_date_count": 0,
            "enriched_nmck_count": 0,
            "public_document_links_found": 0,
            "documents_created": 0,
            "documents_downloaded": 0,
            "extracted_texts_created": 0,
            "failed_count": 0,
            "errors": [],
        }
        for tender in candidates:
            savepoint = self._session.begin_nested() if dry_run else None
            try:
                summary["processed"] += 1
                discovered = self._lookup_public_discovered_item(tender.registry_number, existing_tender=tender)
                detail = self._public_provider.fetch_detail(
                    discovered.card_url or tender.eis_url,
                    registry_number=tender.registry_number,
                )
                if detail.document_links:
                    summary["public_document_links_found"] += len(detail.document_links)
                before_title = tender.title
                before_customer = tender.customer_name
                before_publication_date = tender.publication_date
                before_nmck = tender.nmck_amount
                before_docs = self._repo.count_documents()
                before_extracted = self._repo.count_documents_by_text_status("extracted")

                upsert_data = self._build_upsert_from_discovery(
                    discovered,
                    detail,
                    soap_raw=None,
                    soap_status="backfill_public_only",
                    existing_tender=tender,
                    include_public_documents=with_documents,
                )
                updated_tender = self._repo.upsert_tender(upsert_data.tender)
                if upsert_data.customer:
                    self._repo.upsert_customer(upsert_data.customer)
                for doc_data in upsert_data.documents:
                    doc_data["tender_id"] = updated_tender.id
                    self._repo.upsert_document(doc_data)
                if not dry_run:
                    self._save_public_detail_artifacts(updated_tender, detail)

                if with_documents and not dry_run:
                    docs_result = self.download_documents(updated_tender.id)
                    summary["documents_downloaded"] += docs_result.get("downloaded", 0)

                self._session.flush()
                self._session.refresh(updated_tender)
                if _is_placeholder_title(before_title, tender.registry_number) and not _is_placeholder_title(updated_tender.title, tender.registry_number):
                    summary["enriched_title_count"] += 1
                if not before_customer and updated_tender.customer_name:
                    summary["enriched_customer_count"] += 1
                if not before_publication_date and updated_tender.publication_date:
                    summary["enriched_publication_date_count"] += 1
                if before_nmck is None and updated_tender.nmck_amount is not None:
                    summary["enriched_nmck_count"] += 1
                summary["documents_created"] += max(0, self._repo.count_documents() - before_docs)
                summary["extracted_texts_created"] += max(0, self._repo.count_documents_by_text_status("extracted") - before_extracted)

                if dry_run:
                    savepoint.rollback()
                else:
                    self._session.commit()
            except Exception as exc:
                if dry_run and savepoint is not None:
                    savepoint.rollback()
                else:
                    self._session.rollback()
                summary["failed_count"] += 1
                summary["errors"].append(f"{tender.registry_number}: {exc}")
        return summary

    def _fetch_eis_by_registry_number_safe(
        self,
        registry_number: str,
    ) -> tuple[EisTenderRaw | None, str]:
        try:
            raw = self._eis.fetch_by_registry_number(registry_number)
            if raw is None:
                return None, "not_found"
            return raw, "success"
        except EisNoDataError:
            return None, "no_data"
        except EisMissingTokenError:
            return None, "missing_token"
        except EisConnectionResetError:
            return None, "connection_reset"
        except Exception as exc:
            logger.warning("EIS registry fetch failed for %s: %s", registry_number, exc)
            return None, "error"

    def _lookup_public_discovered_item(self, registry_number: str, existing_tender=None) -> DiscoveredRegistryNumber:
        page = self._public_provider.search(query=registry_number, page_size=10)
        for item in page.items:
            if item.registry_number == registry_number:
                return DiscoveredRegistryNumber(
                    registry_number=item.registry_number,
                    source="external_public_44fz",
                    source_type="external_public_44fz",
                    tender_title=item.title,
                    purchase_number=item.purchase_number,
                    customer_name=item.customer_name,
                    customer_inn=item.customer_inn,
                    customer_kpp=item.customer_kpp,
                    publication_date=item.publication_date,
                    application_deadline=item.application_deadline,
                    nmck_amount=float(item.nmck_amount) if item.nmck_amount is not None else None,
                    law_type=item.law_type,
                    source_url=item.source_url,
                    card_url=item.card_url,
                    raw=item.raw,
                )
        return DiscoveredRegistryNumber(
            registry_number=registry_number,
            source="external_public_44fz",
            source_type="external_public_44fz",
            tender_title=getattr(existing_tender, "title", None),
            purchase_number=getattr(existing_tender, "purchase_number", None),
            customer_name=getattr(existing_tender, "customer_name", None),
            customer_inn=getattr(existing_tender, "customer_inn", None),
            customer_kpp=getattr(existing_tender, "customer_kpp", None),
            publication_date=getattr(existing_tender, "publication_date", None),
            application_deadline=getattr(existing_tender, "application_deadline", None),
            nmck_amount=getattr(existing_tender, "nmck_amount", None),
            law_type=getattr(existing_tender, "law_type", None) or "44fz",
            source_url=getattr(existing_tender, "platform_url", None),
            card_url=getattr(existing_tender, "eis_url", None),
            raw={"lookup_status": page.status, "lookup_error": page.error},
        )

    def _build_upsert_from_discovery(
        self,
        discovered: DiscoveredRegistryNumber,
        detail: PublicTenderDetail,
        soap_raw: EisTenderRaw | None,
        soap_status: str,
        existing_tender=None,
        include_public_documents: bool = True,
    ) -> TenderUpsertData:
        soap_documents = self._load_soap_documents(soap_raw)
        public_documents = [] if soap_documents or not include_public_documents else self._public_documents_to_rows(detail)
        existing_title = None
        if existing_tender is not None and not _is_placeholder_title(existing_tender.title, discovered.registry_number):
            existing_title = existing_tender.title

        soap_title = None
        if soap_raw and soap_raw.title and not _is_placeholder_title(soap_raw.title, discovered.registry_number):
            soap_title = soap_raw.title

        title = _first_non_empty(
            soap_title,
            detail.title,
            discovered.tender_title,
            existing_title,
            f"Закупка {discovered.registry_number}",
        )
        customer_name = _first_non_empty(
            getattr(soap_raw, "customer_name", None),
            detail.customer_name,
            discovered.customer_name,
            getattr(existing_tender, "customer_name", None) if existing_tender is not None else None,
        )
        customer_inn = _first_non_empty(
            getattr(soap_raw, "customer_inn", None),
            detail.customer_inn,
            discovered.customer_inn,
            getattr(existing_tender, "customer_inn", None) if existing_tender is not None else None,
        )
        customer_kpp = _first_non_empty(
            getattr(soap_raw, "customer_kpp", None),
            detail.customer_kpp,
            discovered.customer_kpp,
            getattr(existing_tender, "customer_kpp", None) if existing_tender is not None else None,
        )
        publication_date = _first_non_empty(
            getattr(soap_raw, "publication_date", None),
            detail.publication_date,
            discovered.publication_date,
            getattr(existing_tender, "publication_date", None) if existing_tender is not None else None,
        )
        application_deadline = _first_non_empty(
            getattr(soap_raw, "application_deadline", None),
            detail.application_deadline,
            discovered.application_deadline,
            getattr(existing_tender, "application_deadline", None) if existing_tender is not None else None,
        )
        nmck_amount = _first_non_empty(
            getattr(soap_raw, "nmck_amount", None),
            detail.nmck_amount,
            discovered.nmck_amount,
            getattr(existing_tender, "nmck_amount", None) if existing_tender is not None else None,
        )
        card_url = _first_non_empty(
            getattr(soap_raw, "eis_url", None),
            detail.card_url,
            discovered.card_url,
            getattr(existing_tender, "eis_url", None) if existing_tender is not None else None,
        )
        platform_url = _first_non_empty(
            detail.source_url,
            discovered.source_url,
            getattr(existing_tender, "platform_url", None) if existing_tender is not None else None,
            card_url,
        )
        law_type = _first_non_empty(getattr(soap_raw, "law_type", None), detail.law_type, discovered.law_type, "44fz")
        raw_payload = self._build_merged_raw_payload(discovered, detail, soap_raw, soap_status)

        tender_data = {
            "source": "eis",
            "external_id": discovered.registry_number,
            "registry_number": discovered.registry_number,
            "purchase_number": _first_non_empty(
                getattr(soap_raw, "purchase_number", None),
                discovered.purchase_number,
                getattr(existing_tender, "purchase_number", None) if existing_tender is not None else None,
            ),
            "law_type": _first_non_empty(law_type, getattr(existing_tender, "law_type", None) if existing_tender is not None else None),
            "title": title,
            "description": _first_non_empty(
                getattr(soap_raw, "description", None),
                getattr(existing_tender, "description", None) if existing_tender is not None else None,
            ),
            "customer_name": customer_name,
            "customer_inn": customer_inn,
            "customer_kpp": customer_kpp,
            "region": _first_non_empty(
                getattr(soap_raw, "region", None),
                getattr(existing_tender, "region", None) if existing_tender is not None else None,
            ),
            "platform_name": "zakupki.gov.ru",
            "platform_url": platform_url,
            "eis_url": card_url,
            "nmck_amount": float(nmck_amount) if nmck_amount is not None else None,
            "currency": _first_non_empty(
                getattr(soap_raw, "currency", None),
                getattr(existing_tender, "currency", None) if existing_tender is not None else None,
                "RUB",
            ),
            "publication_date": publication_date,
            "application_deadline": application_deadline,
            "auction_date": _first_non_empty(
                getattr(soap_raw, "auction_date", None),
                getattr(existing_tender, "auction_date", None) if existing_tender is not None else None,
            ),
            "status": _first_non_empty(
                getattr(soap_raw, "status", None),
                getattr(existing_tender, "status", None) if existing_tender is not None else None,
            ),
            "raw_payload": raw_payload,
            "content_hash": content_hash((title or "") + (customer_name or "") + discovered.registry_number),
        }
        customer_data = None
        if customer_name:
            customer_data = {
                "name": customer_name,
                "inn": customer_inn,
                "kpp": customer_kpp,
                "region": getattr(soap_raw, "region", None),
                "raw_last_payload": raw_payload,
            }
        return TenderUpsertData(
            tender=tender_data,
            customer=customer_data,
            documents=soap_documents or public_documents,
        )

    def _load_soap_documents(self, soap_raw: EisTenderRaw | None) -> list[dict[str, Any]]:
        if soap_raw is None:
            return []
        documents = []
        for doc in soap_raw.documents or self._eis.fetch_tender_documents(soap_raw):
            documents.append({
                "source_document_id": doc.source_document_id,
                "file_name": doc.file_name,
                "file_url": doc.file_url,
                "content_type": doc.content_type,
                "size_bytes": doc.size_bytes,
                "raw_meta": doc.raw_meta,
            })
        return documents

    def _public_documents_to_rows(self, detail: PublicTenderDetail) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for link in detail.document_links:
            source_document_id = (link.raw or {}).get("uid")
            rows.append({
                "source_document_id": source_document_id or link.url,
                "file_name": link.file_name or link.title or _derive_doc_name_from_url(link.url),
                "file_url": link.url,
                "content_type": link.content_type,
                "size_bytes": link.size_bytes,
                "download_status": "pending",
                "text_extraction_status": "pending",
                "raw_meta": {
                    "source": "external_public_223fz_detail" if detail.law_type == "223fz" else "external_public_44fz_detail",
                    "title": link.title,
                    "card_url": detail.card_url,
                    "raw": link.raw,
                },
            })
        return rows

    def _build_merged_raw_payload(
        self,
        discovered: DiscoveredRegistryNumber,
        detail: PublicTenderDetail,
        soap_raw: EisTenderRaw | None,
        soap_status: str,
    ) -> dict[str, Any]:
        payload = {
            "merge_priority": ["soap", "public_detail", "public_search", "fallback"],
            "soap_status": soap_status,
            "discovery": _json_safe_discovered(discovered),
            "public_detail": _json_safe_detail(detail),
        }
        if soap_raw and soap_raw.raw_payload is not None:
            payload["soap_raw_payload"] = soap_raw.raw_payload
        return payload

    def _save_public_detail_artifacts(self, tender, detail: PublicTenderDetail) -> None:
        raw_dir = (
            Path(self._config.data_dir)
            / "tenders"
            / "eis"
            / _safe_dirname(tender.external_id)
            / "raw"
        )
        raw_dir.mkdir(parents=True, exist_ok=True)
        artifacts = [
            ("public_detail_common_info", detail.common_info_html, "public_detail_common_info.html"),
            ("public_detail_documents", detail.documents_html, "public_detail_documents.html"),
        ]
        for artifact_type, html_content, file_name in artifacts:
            if not html_content:
                continue
            local_path = raw_dir / file_name
            local_path.write_text(html_content, encoding="utf-8")
            self._repo.upsert_artifact({
                "tender_id": tender.id,
                "artifact_type": artifact_type,
                "source": "external_public_44fz",
                "local_path": str(local_path),
                "sha256": hashlib.sha256(html_content.encode("utf-8")).hexdigest(),
                "size_bytes": local_path.stat().st_size,
                "content_type": "text/html",
                "raw_meta": {
                    "registry_number": detail.registry_number,
                    "card_url": detail.card_url,
                    "source_url": detail.source_url,
                },
            })

    # ── Step 2: Download documents ──

    def download_documents(self, tender_id: str) -> dict[str, int]:
        tender = self._repo.get_tender_by_id(tender_id)
        if not tender:
            return {"downloaded": 0, "failed": 0, "error": "Tender not found"}
        self._session.refresh(tender)
        result = download_tender_documents(self._repo, tender, self._config)
        self._session.commit()
        return result

    # ── Step 3: Build search queries ──

    def build_search_queries(self, tender_id: str) -> int:
        tender = self._repo.get_tender_by_id(tender_id)
        if not tender:
            return 0
        queries = build_search_queries(
            tender_title=tender.title,
            customer_name=tender.customer_name,
            customer_inn=tender.customer_inn,
            registry_number=tender.registry_number,
            purchase_number=tender.purchase_number,
            max_queries=self._config.web_search_max_queries_per_tender,
        )
        count = 0
        for q in queries:
            q.provider = self._config.web_search_provider
            self._repo.upsert_search_query({
                "tender_id": tender.id,
                "query": q.query,
                "query_type": q.query_type,
                "provider": q.provider,
            })
            count += 1
        self._session.commit()
        return count

    # ── Step 4: Run web search ──

    def run_web_search(self, tender_id: str) -> int:
        tender = self._repo.get_tender_by_id(tender_id)
        if not tender or not self._config.web_search_enabled:
            return 0
        pending = self._repo.list_pending_search_queries(tender.id, self._config.web_search_provider)
        total = 0
        for sq in pending:
            self._search_limiter.wait()
            try:
                results = self._search_provider.search(
                    sq.query,
                    limit=self._config.web_search_max_results_per_query,
                )
                for r in results:
                    self._repo.upsert_search_result({
                        "tender_id": tender.id,
                        "query_id": sq.id,
                        "provider": sq.provider,
                        "rank": r.rank,
                        "title": r.title,
                        "url": r.url,
                        "normalized_url": r.normalized_url,
                        "snippet": r.snippet,
                        "display_url": r.display_url,
                        "raw_result": r.raw_result,
                        "url_hash": r.url_hash or url_hash(r.normalized_url),
                    })
                    total += 1
                sq.status = "done"
                sq.results_count = len(results)
                sq.executed_at = datetime.now(timezone.utc)
            except Exception as e:
                sq.status = "failed"
                sq.error_message = str(e)
            self._session.flush()
        self._session.commit()
        return total

    # ── Step 5: Fetch search result pages ──

    def fetch_search_results(self, tender_id: str, max_pages: int | None = None) -> dict[str, int]:
        tender = self._repo.get_tender_by_id(tender_id)
        if not tender or not self._config.web_fetch_enabled:
            return {"fetched": 0, "failed": 0}
        max_pages = max_pages or self._config.web_fetch_max_pages_per_tender
        results = self._repo.list_unfetched_results(tender.id, max_results=max_pages)
        fetched = 0
        failed = 0
        for sr in results:
            self._fetch_limiter.wait()
            fetch_result = self._web_fetcher.fetch(
                sr.url,
                timeout=self._config.web_fetch_timeout_seconds,
                max_size_mb=self._config.web_fetch_max_file_size_mb,
            )
            wp_path = self._save_web_page(tender, fetch_result)
            wp_path["search_result_id"] = sr.id
            self._repo.upsert_web_page(wp_path)
            if fetch_result.status == "fetched":
                fetched += 1
            else:
                failed += 1
            self._session.flush()
        self._session.commit()
        return {"fetched": fetched, "failed": failed}

    # ── Run full pipeline for one tender ──

    def run_full(self, tender_id: str) -> dict[str, int | str]:
        result: dict[str, int | str] = {"tender_id": tender_id}
        try:
            docs = self.download_documents(tender_id)
            result["documents_downloaded"] = docs.get("downloaded", 0)
            result["documents_failed"] = docs.get("failed", 0)
        except Exception as e:
            result["documents_error"] = str(e)

        try:
            queries_built = self.build_search_queries(tender_id)
            result["queries_built"] = queries_built
        except Exception as e:
            result["queries_error"] = str(e)

        try:
            search_results = self.run_web_search(tender_id)
            result["search_results_saved"] = search_results
        except Exception as e:
            result["search_error"] = str(e)

        try:
            pages = self.fetch_search_results(tender_id)
            result["pages_fetched"] = pages.get("fetched", 0)
            result["pages_failed"] = pages.get("failed", 0)
        except Exception as e:
            result["fetch_error"] = str(e)

        return result

    # ── Run batch ──

    def run_batch(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int | None = None,
        law_type: str | None = None,
        query: str | None = None,
        web_search: bool = False,
    ) -> list[dict[str, int | str]]:
        batch_limit = limit or self._config.batch_limit
        raw_tenders = self._eis.fetch_tenders(
            date_from=date_from,
            date_to=date_to,
            limit=batch_limit,
            law_type=law_type,
            query=query,
        )
        results: list[dict[str, int | str]] = []
        for raw in raw_tenders:
            try:
                upsert_data = self._normalize_tender(raw)
                tender = self._repo.upsert_tender(upsert_data.tender)
                if upsert_data.customer:
                    self._repo.upsert_customer(upsert_data.customer)
                for doc_data in upsert_data.documents:
                    doc_data["tender_id"] = tender.id
                    self._repo.upsert_document(doc_data)
                self._save_raw_payload(tender, raw)
                self._session.commit()
            except Exception as e:
                logger.error("Failed to save tender %s: %s", raw.external_id, e)
                results.append({"tender_id": raw.external_id, "error": str(e)})
                continue

            r = self.run_full(tender.id)
            r["external_id"] = raw.external_id
            r["title"] = tender.title
            results.append(r)

        return results

    # ── Normalization ──

    def _normalize_tender(self, raw: EisTenderRaw) -> TenderUpsertData:
        from src.tender_research.schemas import TenderUpsertData  # noqa

        tender_data = {
            "source": "eis",
            "external_id": raw.external_id,
            "registry_number": raw.registry_number,
            "purchase_number": raw.purchase_number,
            "law_type": raw.law_type,
            "title": raw.title,
            "description": raw.description,
            "customer_name": raw.customer_name,
            "customer_inn": raw.customer_inn,
            "customer_kpp": raw.customer_kpp,
            "region": raw.region,
            "nmck_amount": raw.nmck_amount,
            "currency": raw.currency,
            "publication_date": raw.publication_date,
            "application_deadline": raw.application_deadline,
            "auction_date": raw.auction_date,
            "status": raw.status,
            "eis_url": raw.eis_url,
            "raw_payload": raw.raw_payload,
        }
        hash_payload = {
            key: value
            for key, value in tender_data.items()
            if key != "raw_payload"
        }
        tender_data["content_hash"] = content_hash(
            json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        )

        customer_data = None
        if raw.customer_name:
            customer_data = {
                "name": raw.customer_name,
                "inn": raw.customer_inn,
                "kpp": raw.customer_kpp,
                "region": raw.region,
                "raw_last_payload": raw.raw_payload,
            }

        documents = []
        for doc in raw.documents or self._eis.fetch_tender_documents(raw):
            documents.append({
                "source_document_id": doc.source_document_id,
                "file_name": doc.file_name,
                "file_url": doc.file_url,
                "content_type": doc.content_type,
                "size_bytes": doc.size_bytes,
                "raw_meta": doc.raw_meta,
            })

        return TenderUpsertData(
            tender=tender_data,
            customer=customer_data,
            documents=documents,
        )

    def _save_raw_payload(self, tender: ProcurementTender, raw: EisTenderRaw) -> None:
        tender_dir = (
            Path(self._config.data_dir)
            / "tenders"
            / "eis"
            / _safe_dirname(raw.external_id)
            / "raw"
        )
        tender_dir.mkdir(parents=True, exist_ok=True)
        payload_path = tender_dir / "eis_payload.json"
        if payload_path.exists():
            existing = json.loads(payload_path.read_text(encoding="utf-8"))
            existing["last_seen_at"] = datetime.now(timezone.utc).isoformat()
            payload_path.write_text(
                json.dumps(existing, ensure_ascii=False, default=str), encoding="utf-8"
            )
            return
        raw_dict = {
            "external_id": raw.external_id,
            "title": raw.title,
            "customer_name": raw.customer_name,
            "customer_inn": raw.customer_inn,
            "law_type": raw.law_type,
            "nmck_amount": raw.nmck_amount,
            "publication_date": str(raw.publication_date) if raw.publication_date else None,
            "application_deadline": str(raw.application_deadline) if raw.application_deadline else None,
            "raw_payload": raw.raw_payload,
            "first_seen_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_path.write_text(
            json.dumps(raw_dict, ensure_ascii=False, default=str), encoding="utf-8"
        )
        self._repo.upsert_artifact({
            "tender_id": tender.id,
            "artifact_type": "eis_payload",
            "source": "eis",
            "local_path": str(payload_path),
            "sha256": hashlib.sha256(
                json.dumps(raw_dict, ensure_ascii=False, default=str).encode()
            ).hexdigest(),
            "size_bytes": payload_path.stat().st_size,
            "content_type": "application/json",
        })

    def _save_web_page(self, tender: ProcurementTender, fr: FetchResult) -> dict:
        tender_dir = (
            Path(self._config.data_dir)
            / "tenders"
            / "eis"
            / _safe_dirname(tender.external_id)
            / "web"
        )
        html_dir = tender_dir / "pages"
        text_dir = tender_dir / "extracted_text"
        html_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)

        html_path = None
        text_path = None
        if fr.html:
            html_path = html_dir / f"{fr.url_hash}.html"
            html_path.write_text(fr.html, encoding="utf-8")
        if fr.extracted_text:
            text_path = text_dir / f"{fr.url_hash}.txt"
            text_path.write_text(fr.extracted_text, encoding="utf-8")

        return {
            "tender_id": tender.id,
            "url": fr.url,
            "normalized_url": fr.normalized_url,
            "url_hash": fr.url_hash,
            "fetcher": fr.fetcher,
            "fetch_status": fr.status,
            "http_status": fr.http_status,
            "content_type": fr.content_type,
            "final_url": fr.final_url,
            "html_path": str(html_path) if html_path else None,
            "text_path": str(text_path) if text_path else None,
            "extracted_title": fr.extracted_title,
            "extracted_text_chars": len(fr.extracted_text) if fr.extracted_text else None,
            "raw_meta": {},
            "error_message": fr.error_message,
            "fetched_at": datetime.now(timezone.utc),
        }


def _safe_dirname(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "_-")[:100] or "unknown"


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _is_placeholder_title(title: str | None, registry_number: str | None) -> bool:
    if not title:
        return False
    cleaned = title.strip()
    if registry_number and cleaned == f"Закупка {registry_number}":
        return True
    return bool(re.fullmatch(r"Закупка\s+\d{11,25}", cleaned))


def _json_safe_discovered(discovered: DiscoveredRegistryNumber) -> dict[str, Any]:
    return {
        "registry_number": discovered.registry_number,
        "purchase_number": discovered.purchase_number,
        "title": discovered.tender_title,
        "customer_name": discovered.customer_name,
        "customer_inn": discovered.customer_inn,
        "customer_kpp": discovered.customer_kpp,
        "publication_date": discovered.publication_date.isoformat() if discovered.publication_date else None,
        "application_deadline": discovered.application_deadline.isoformat() if discovered.application_deadline else None,
        "nmck_amount": discovered.nmck_amount,
        "law_type": discovered.law_type,
        "source_url": discovered.source_url,
        "card_url": discovered.card_url,
        "raw": discovered.raw,
    }


def _json_safe_detail(detail: PublicTenderDetail) -> dict[str, Any]:
    return {
        "registry_number": detail.registry_number,
        "title": detail.title,
        "customer_name": detail.customer_name,
        "customer_inn": detail.customer_inn,
        "customer_kpp": detail.customer_kpp,
        "publication_date": detail.publication_date.isoformat() if detail.publication_date else None,
        "application_deadline": detail.application_deadline.isoformat() if detail.application_deadline else None,
        "nmck_amount": float(detail.nmck_amount) if detail.nmck_amount is not None else None,
        "law_type": detail.law_type,
        "card_url": detail.card_url,
        "source_url": detail.source_url,
        "document_links": [
            {
                "title": link.title,
                "file_name": link.file_name,
                "url": link.url,
                "content_type": link.content_type,
                "size_bytes": link.size_bytes,
                "size_text": link.size_text,
                "raw": link.raw,
            }
            for link in detail.document_links
        ],
        "network_status": detail.network_status,
        "error_message": detail.error_message,
    }


def _derive_doc_name_from_url(url: str) -> str:
    match = re.search(r"/([^/?#]+)(?:\?|$)", url)
    if match:
        return match.group(1)
    return "document"
