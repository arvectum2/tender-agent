from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.tender_research.config import TenderResearchConfig
from src.tender_research.eis_loader import EisTenderLoader
from src.tender_research.errors import DiscoveryEmptyError, DiscoveryError
from src.tender_research.providers.public_223fz_search import Public223FzSearchProvider
from src.tender_research.providers.public_44fz_search import (
    Public44FzSearchProvider,
    PublicSearchStatus,
    PublicTenderSearchPage,
    PublicTenderSearchItem,
    _parse_public_datetime,
)

logger = logging.getLogger(__name__)

_REGISTRY_NUMBER_RE = re.compile(r"\b(\d{19})\b")
_EIS_URL_RE = re.compile(r"regNumber=(\d{19})")


class SourceType:
    BACKEND_SEARCH_REAL = "backend_search_real"
    EXTERNAL_PUBLIC_44FZ = "external_public_44fz"
    EXTERNAL_PUBLIC_223FZ = "external_public_223fz"
    LOCAL_DB = "local_db"
    SEED_FILE = "seed_file"
    DEMO = "demo"
    UNAVAILABLE = "unavailable"
    NONE = "none"


@dataclass
class DiscoveredRegistryNumber:
    registry_number: str
    source: str = ""
    source_type: str = SourceType.NONE
    tender_title: str | None = None
    purchase_number: str | None = None
    customer_name: str | None = None
    customer_inn: str | None = None
    customer_kpp: str | None = None
    publication_date: datetime | None = None
    application_deadline: datetime | None = None
    nmck_amount: float | None = None
    law_type: str | None = "44fz"
    source_url: str | None = None
    card_url: str | None = None
    raw: dict | None = None
    external_id: str | None = None
    is_demo: bool = False


@dataclass
class DiscoveryResult:
    numbers: list[DiscoveredRegistryNumber]
    selected_source: str
    selected_source_type: str = SourceType.NONE
    is_demo: bool = False
    requested_limit: int | None = None
    effective_limit: int | None = None
    requested_page_size: int = 0
    effective_page_size: int = 0
    date_from: datetime | None = None
    date_to: datetime | None = None
    pages_read: int = 0
    page_size: int = 0
    source_url: str | None = None
    discovered_count: int = 0
    items_raw_count: int = 0
    items_with_registry_number: int = 0
    skipped_without_registry_number: int = 0
    items_after_dedupe: int = 0
    items_after_demo_filter: int = 0
    network_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_registry_numbers_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    numbers: list[str] = []
    for match in _EIS_URL_RE.finditer(html):
        rn = match.group(1)
        if rn not in seen:
            seen.add(rn)
            numbers.append(rn)
    if not numbers:
        for match in _REGISTRY_NUMBER_RE.finditer(html):
            rn = match.group(1)
            if rn not in seen:
                seen.add(rn)
                numbers.append(rn)
    return numbers


def _coerce_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _search_item_to_discovered(item: PublicTenderSearchItem) -> DiscoveredRegistryNumber | None:
    if not item.registry_number:
        return None
    return DiscoveredRegistryNumber(
        registry_number=item.registry_number,
        source="external_public_223fz" if item.law_type == "223fz" else "external_public_44fz",
        source_type=SourceType.EXTERNAL_PUBLIC_223FZ if item.law_type == "223fz" else SourceType.EXTERNAL_PUBLIC_44FZ,
        tender_title=item.title,
        purchase_number=item.purchase_number,
        customer_name=item.customer_name,
        customer_inn=item.customer_inn,
        customer_kpp=item.customer_kpp,
        publication_date=item.publication_date,
        application_deadline=item.application_deadline,
        nmck_amount=_coerce_float(item.nmck_amount),
        law_type=item.law_type,
        source_url=item.source_url,
        card_url=item.card_url,
        raw=item.raw,
        external_id=item.purchase_number or item.registry_number,
        is_demo=item.is_demo,
    )


def _page_item_metrics(pages: list[PublicTenderSearchPage]) -> dict[str, int]:
    items_raw_count = 0
    items_with_registry_number = 0
    skipped_without_registry_number = 0
    deduped_numbers: set[str] = set()
    demo_filtered_numbers: set[str] = set()
    for page_obj in pages:
        for item in page_obj.items:
            items_raw_count += 1
            if item.registry_number:
                items_with_registry_number += 1
                deduped_numbers.add(item.registry_number)
                if not item.is_demo:
                    demo_filtered_numbers.add(item.registry_number)
            else:
                skipped_without_registry_number += 1
    return {
        "items_raw_count": items_raw_count,
        "items_with_registry_number": items_with_registry_number,
        "skipped_without_registry_number": skipped_without_registry_number,
        "items_after_dedupe": len(deduped_numbers),
        "items_after_demo_filter": len(demo_filtered_numbers),
    }


class RegistryNumberDiscovery:
    def __init__(
        self,
        config: TenderResearchConfig | None = None,
        eis_loader: EisTenderLoader | None = None,
    ):
        self._config = config or TenderResearchConfig()
        self._eis = eis_loader or EisTenderLoader(
            mode=self._config.eis_mode,
            discovery_mode=self._config.eis_discovery_mode,
        )
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

    def discover(
        self,
        source: str = "auto",
        days_back: int | None = None,
        limit: int | None = None,
        seed_file: str | None = None,
        page_size: int = 30,
    ) -> DiscoveryResult:
        source = source or self._config.registry_discovery_source
        days_back = days_back if days_back is not None else self._config.registry_discovery_days_back
        limit = limit if limit is not None else self._config.registry_discovery_limit
        page_size = max(1, page_size)

        if source in ("auto", "auto_discover"):
            return self._auto_discover(days_back=days_back, limit=limit, seed_file=seed_file, page_size=page_size)
        elif source == "external_public_44fz":
            return self._external_public_44fz(days_back=days_back, limit=limit, page_size=page_size)
        elif source == "external_public_223fz":
            return self._external_public_223fz(days_back=days_back, limit=limit, page_size=page_size)
        elif source == "seed_file":
            return self._seed_file(limit=limit, seed_file=seed_file)
        elif source == "local_db":
            return self._local_db(days_back=days_back, limit=limit)
        elif source == "demo":
            return self._demo_discover(days_back=days_back, limit=limit)
        elif source in ("backend_search", "backend_search_real"):
            return self._backend_search_real(days_back=days_back, limit=limit)
        else:
            msg = f"Unknown discovery source: {source}"
            raise DiscoveryError(msg)

    def _auto_discover(
        self,
        days_back: int,
        limit: int,
        seed_file: str | None,
        page_size: int,
    ) -> DiscoveryResult:
        warnings: list[str] = []

        result = self._external_public_44fz(days_back=days_back, limit=limit, page_size=page_size)
        if result.numbers and not result.is_demo:
            result.warnings = warnings
            return result
        if result.network_status in (PublicSearchStatus.BLOCKED, PublicSearchStatus.TIMEOUT, PublicSearchStatus.BAD_GATEWAY):
            warnings.append(f"external_public_44fz is blocked in current network: {result.network_status}")

        result = self._seed_file(limit=limit, seed_file=seed_file)
        if result.numbers:
            result.warnings = warnings
            return result

        if self._config.allow_demo_discovery:
            warnings.append("No real data found, using demo as fallback")
            result = self._demo_discover(days_back=days_back, limit=limit)
            result.warnings = warnings
            return result

        warnings.append("No real data found and allow_demo_discovery is false")
        return DiscoveryResult(
            numbers=[],
            selected_source="auto",
            selected_source_type=SourceType.NONE,
            warnings=warnings,
            network_status="no_source_available",
        )

    def _external_public_44fz(
        self,
        days_back: int,
        limit: int,
        page_size: int = 30,
    ) -> DiscoveryResult:
        effective_page_size = min(max(page_size, 1), 100)
        effective_limit = max(0, limit)
        date_from = datetime.now(timezone.utc).date() - timedelta(days=days_back)
        date_to = datetime.now(timezone.utc).date()
        max_pages = max(1, (effective_limit + effective_page_size - 1) // effective_page_size)
        max_pages = min(max_pages, 10)

        pages = self._public_provider.search_pages(
            query=None,
            date_from=date_from,
            date_to=date_to,
            max_pages=max_pages,
            page_size=effective_page_size,
        )
        metrics = _page_item_metrics(pages)
        source_url = pages[0].source_url if pages else None

        first_status = pages[0].status if pages else PublicSearchStatus.EMPTY
        network_status = first_status
        if first_status not in (PublicSearchStatus.SUCCESS, PublicSearchStatus.EMPTY):
            return DiscoveryResult(
                numbers=[],
                selected_source="external_public_44fz",
                selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
                requested_limit=limit,
                effective_limit=effective_limit,
                requested_page_size=page_size,
                effective_page_size=effective_page_size,
                date_from=datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
                date_to=datetime.combine(date_to, datetime.min.time(), tzinfo=timezone.utc),
                pages_read=0,
                page_size=effective_page_size,
                source_url=source_url,
                items_raw_count=metrics["items_raw_count"],
                items_with_registry_number=metrics["items_with_registry_number"],
                skipped_without_registry_number=metrics["skipped_without_registry_number"],
                items_after_dedupe=metrics["items_after_dedupe"],
                items_after_demo_filter=metrics["items_after_demo_filter"],
                network_status=first_status,
                errors=[pages[0].error or f"Network status: {first_status}"] if pages else [],
                warnings=[f"external_public_44fz is {first_status}: {pages[0].error}" if pages else f"external_public_44fz is {first_status}"],
            )

        discovered = self._page_items_to_discovered(pages, effective_limit or None)
        numbers = [item.registry_number for item in discovered]

        successes = sum(1 for p in pages if p.status == PublicSearchStatus.SUCCESS)
        return DiscoveryResult(
            numbers=discovered,
            selected_source="external_public_44fz",
            selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
            requested_limit=limit,
            effective_limit=effective_limit,
            requested_page_size=page_size,
            effective_page_size=effective_page_size,
            date_from=datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
            date_to=datetime.combine(date_to, datetime.min.time(), tzinfo=timezone.utc),
            pages_read=len(pages),
            page_size=effective_page_size,
            source_url=source_url,
            discovered_count=len(discovered),
            items_raw_count=metrics["items_raw_count"],
            items_with_registry_number=metrics["items_with_registry_number"],
            skipped_without_registry_number=metrics["skipped_without_registry_number"],
            items_after_dedupe=metrics["items_after_dedupe"],
            items_after_demo_filter=len(numbers),
            network_status=network_status,
            errors=[],
            warnings=[f"external_public_44fz read {len(pages)} pages, found {len(numbers)} numbers, {len(pages) - successes} pages non-success"],
        )

    def _external_public_223fz(
        self,
        days_back: int,
        limit: int,
        page_size: int = 30,
    ) -> DiscoveryResult:
        effective_page_size = min(max(page_size, 1), 100)
        effective_limit = max(0, limit)
        date_from = datetime.now(timezone.utc).date() - timedelta(days=days_back)
        date_to = datetime.now(timezone.utc).date()
        max_pages = max(1, (effective_limit + effective_page_size - 1) // effective_page_size)
        max_pages = min(max_pages, 10)

        pages = self._public_223fz_provider.search_pages(
            query=None,
            date_from=date_from,
            date_to=date_to,
            max_pages=max_pages,
            page_size=effective_page_size,
        )
        metrics = _page_item_metrics(pages)
        source_url = pages[0].source_url if pages else None

        first_status = pages[0].status if pages else PublicSearchStatus.EMPTY
        network_status = first_status
        if first_status not in (PublicSearchStatus.SUCCESS, PublicSearchStatus.EMPTY):
            return DiscoveryResult(
                numbers=[],
                selected_source="external_public_223fz",
                selected_source_type=SourceType.EXTERNAL_PUBLIC_223FZ,
                requested_limit=limit,
                effective_limit=effective_limit,
                requested_page_size=page_size,
                effective_page_size=effective_page_size,
                date_from=datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
                date_to=datetime.combine(date_to, datetime.min.time(), tzinfo=timezone.utc),
                pages_read=0,
                page_size=effective_page_size,
                source_url=source_url,
                items_raw_count=metrics["items_raw_count"],
                items_with_registry_number=metrics["items_with_registry_number"],
                skipped_without_registry_number=metrics["skipped_without_registry_number"],
                items_after_dedupe=metrics["items_after_dedupe"],
                items_after_demo_filter=metrics["items_after_demo_filter"],
                network_status=first_status,
                errors=[pages[0].error or f"Network status: {first_status}"] if pages else [],
                warnings=[f"external_public_223fz is {first_status}: {pages[0].error}" if pages else f"external_public_223fz is {first_status}"],
            )

        discovered = self._page_items_to_discovered(pages, effective_limit or None)
        numbers = [item.registry_number for item in discovered]

        successes = sum(1 for p in pages if p.status == PublicSearchStatus.SUCCESS)
        return DiscoveryResult(
            numbers=discovered,
            selected_source="external_public_223fz",
            selected_source_type=SourceType.EXTERNAL_PUBLIC_223FZ,
            requested_limit=limit,
            effective_limit=effective_limit,
            requested_page_size=page_size,
            effective_page_size=effective_page_size,
            date_from=datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
            date_to=datetime.combine(date_to, datetime.min.time(), tzinfo=timezone.utc),
            pages_read=len(pages),
            page_size=effective_page_size,
            source_url=source_url,
            discovered_count=len(discovered),
            items_raw_count=metrics["items_raw_count"],
            items_with_registry_number=metrics["items_with_registry_number"],
            skipped_without_registry_number=metrics["skipped_without_registry_number"],
            items_after_dedupe=metrics["items_after_dedupe"],
            items_after_demo_filter=len(numbers),
            network_status=network_status,
            errors=[],
            warnings=[f"external_public_223fz read {len(pages)} pages, found {len(numbers)} numbers, {len(pages) - successes} pages non-success"],
        )

    def _seed_file(
        self,
        limit: int | None = None,
        seed_file: str | None = None,
    ) -> DiscoveryResult:
        seed_path_str = seed_file or self._config.eis_seed_file
        seed_path = Path(seed_path_str)
        if not seed_path.exists():
            msg = f"Seed file not found: {seed_path}"
            logger.warning(msg)
            return DiscoveryResult(
                numbers=[],
                selected_source="seed_file",
                selected_source_type=SourceType.SEED_FILE,
                warnings=[msg],
            )

        if seed_path.suffix.lower() == ".json":
            return self._seed_from_json(seed_path, limit)

        lines = [
            line.strip() for line in seed_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            return DiscoveryResult(
                numbers=[],
                selected_source="seed_file",
                selected_source_type=SourceType.SEED_FILE,
            )
        selected = lines[:limit] if limit else lines
        numbers = [
            DiscoveredRegistryNumber(registry_number=rn, source="seed_file", source_type=SourceType.SEED_FILE)
            for rn in selected
        ]
        return DiscoveryResult(
            numbers=numbers,
            selected_source="seed_file",
            selected_source_type=SourceType.SEED_FILE,
            requested_limit=limit,
            effective_limit=len(numbers),
            discovered_count=len(numbers),
        )

    def _seed_from_json(self, seed_path: Path, limit: int | None = None) -> DiscoveryResult:
        try:
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return DiscoveryResult(
                numbers=[],
                selected_source="seed_file",
                selected_source_type=SourceType.SEED_FILE,
                errors=[f"Failed to parse JSON seed: {exc}"],
            )
        if isinstance(raw, dict):
            items = raw.get("items", raw.get("numbers", []))
        elif isinstance(raw, list):
            items = raw
        else:
            return DiscoveryResult(
                numbers=[],
                selected_source="seed_file",
                selected_source_type=SourceType.SEED_FILE,
                errors=["Unexpected JSON seed format, expected list or dict with items/numbers"],
            )
        if limit:
            items = items[:limit]
        numbers: list[DiscoveredRegistryNumber] = []
        for item in items:
            if isinstance(item, str):
                numbers.append(DiscoveredRegistryNumber(registry_number=item, source="seed_file", source_type=SourceType.SEED_FILE))
            elif isinstance(item, dict):
                rn = item.get("registry_number", item.get("reestr_number", item.get("number", "")))
                if rn:
                    numbers.append(DiscoveredRegistryNumber(
                        registry_number=str(rn),
                        source="seed_file",
                        source_type=SourceType.SEED_FILE,
                        tender_title=item.get("title"),
                        purchase_number=item.get("purchase_number"),
                        customer_name=item.get("customer_name"),
                        customer_inn=item.get("customer_inn"),
                        customer_kpp=item.get("customer_kpp"),
                        publication_date=_parse_public_datetime(item.get("publication_date")) if item.get("publication_date") else None,
                        application_deadline=_parse_public_datetime(item.get("application_deadline") or item.get("deadline")) if item.get("application_deadline") or item.get("deadline") else None,
                        nmck_amount=_coerce_float(item.get("nmck_amount") or item.get("initial_price")),
                        law_type=item.get("law_type") or item.get("law") or "44fz",
                        source_url=item.get("source_url"),
                        card_url=item.get("card_url") or item.get("source_url"),
                        raw=item,
                        external_id=item.get("purchase_number"),
                    ))
        return DiscoveryResult(
            numbers=numbers,
            selected_source="seed_file",
            selected_source_type=SourceType.SEED_FILE,
            requested_limit=limit,
            effective_limit=len(numbers),
            discovered_count=len(numbers),
        )

    @staticmethod
    def _page_items_to_discovered(
        pages: list[PublicTenderSearchPage],
        limit: int | None,
    ) -> list[DiscoveredRegistryNumber]:
        discovered: list[DiscoveredRegistryNumber] = []
        seen: set[str] = set()
        for page_obj in pages:
            for item in page_obj.items:
                discovered_item = _search_item_to_discovered(item)
                if not discovered_item or discovered_item.registry_number in seen:
                    continue
                seen.add(discovered_item.registry_number)
                discovered.append(discovered_item)
                if limit and len(discovered) >= limit:
                    return discovered
        return discovered

    def _local_db(
        self,
        days_back: int,
        limit: int,
    ) -> DiscoveryResult:
        date_from = datetime.now(timezone.utc) - timedelta(days=days_back)
        try:
            from src.tender_research.pipeline_utils import get_tenders_from_repo
            tenders = get_tenders_from_repo(date_from=date_from, limit=limit)
        except Exception as exc:
            return DiscoveryResult(
                numbers=[],
                selected_source="local_db",
                selected_source_type=SourceType.LOCAL_DB,
                errors=[f"Failed to query local database: {exc}"],
            )
        numbers: list[DiscoveredRegistryNumber] = []
        for t in tenders:
            rn = getattr(t, "registry_number", None)
            if rn:
                numbers.append(DiscoveredRegistryNumber(
                    registry_number=rn,
                    source="local_db",
                    source_type=SourceType.LOCAL_DB,
                    tender_title=getattr(t, "title", None),
                    external_id=getattr(t, "external_id", None),
                ))
        return DiscoveryResult(
            numbers=numbers,
            selected_source="local_db",
            selected_source_type=SourceType.LOCAL_DB,
            requested_limit=limit,
            effective_limit=len(numbers),
            discovered_count=len(numbers),
        )

    def _backend_search_real(self, days_back: int, limit: int) -> DiscoveryResult:
        return DiscoveryResult(
            numbers=[],
            selected_source="backend_search_real",
            selected_source_type=SourceType.UNAVAILABLE,
            warnings=["backend_search_real is not implemented yet (no working external backend search endpoint)"],
            network_status="not_available",
        )

    def _demo_discover(self, days_back: int, limit: int) -> DiscoveryResult:
        date_from = datetime.now(timezone.utc) - timedelta(days=days_back)
        raw_tenders = self._eis.fetch_tenders(
            date_from=date_from,
            limit=limit,
        )
        numbers: list[DiscoveredRegistryNumber] = []
        skipped = 0
        for raw in raw_tenders:
            if raw.registry_number:
                numbers.append(DiscoveredRegistryNumber(
                    registry_number=raw.registry_number,
                    source="demo",
                    source_type=SourceType.DEMO,
                    tender_title=raw.title,
                    external_id=raw.external_id,
                    is_demo=True,
                ))
            else:
                skipped += 1
        return DiscoveryResult(
            numbers=numbers,
            selected_source="demo",
            selected_source_type=SourceType.DEMO,
            is_demo=True,
            requested_limit=limit,
            effective_limit=len(numbers),
            discovered_count=len(numbers),
            skipped_without_registry_number=skipped,
        )
