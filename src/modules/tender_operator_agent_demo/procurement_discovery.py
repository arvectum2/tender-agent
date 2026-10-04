from __future__ import annotations

import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementAttachment,
    ProcurementDetails,
    ProcurementSearchOutcome,
    ProcurementSourceStatus,
    PublicProcurementSearchResponse,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementSearchRequest as ProcurementSearchRequestV2,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementSearchResult as ProcurementSearchResultV2,
)
from src.modules.tender_operator_agent_demo.procurement_sources import (
    DemoProcurementRecord,
    get_demo_local_procurements,
    get_procurement_source_descriptors,
)
from src.modules.tender_operator_agent_demo.public_44fz_parser import (
    Public44FzSearchStatus,
    extract_public_search_total_count,
    fetch_public_44fz_search_page,
    parse_44fz_search_results,
)
from src.modules.tender_operator_agent_demo.public_44fz_search import (
    Public44FzSearchProvider,
    build_public_eis_search_url,
    normalize_public_eis_law,
    resolve_public_eis_stage_flag,
)
from src.modules.tender_operator_agent_demo.relevance_scoring import (
    score_procurement_card,
)
from src.modules.tender_operator_agent_demo.schemas import (
    ProcurementSearchResponse,
    ProcurementSearchResult,
    PublicSearchUrlResponse,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.supplier_profile import SupplierProfile

DEFAULT_SEARCH_PAGE_SIZE = 10
MAX_BACKFILL_PAGES = 10


def _encode_search_cursor(
    query: str,
    filters: dict[str, Any],
    next_eis_page: int,
    seen_registry_numbers: list[str],
    page_size: int,
    ui_page: int = 1,
) -> str:
    payload = {
        "v": 1,
        "q": query,
        "f": filters,
        "ep": next_eis_page,
        "sn": seen_registry_numbers,
        "ps": page_size,
        "up": ui_page,
    }
    return base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).decode("ascii")


def _decode_search_cursor(raw: str) -> dict[str, Any] | None:
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        payload = json.loads(decoded)
        if not isinstance(payload, dict) or payload.get("v") != 1:
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _build_cursor_filters(
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
    status_filter: str | None = None,
    procedure_type: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    law: str = "44fz",
) -> dict[str, Any]:
    out: dict[str, Any] = {"law": law}
    if region:
        out["region"] = region
    if date_from:
        out["date_from"] = date_from
    if date_to:
        out["date_to"] = date_to
    if price_from is not None:
        out["price_from"] = price_from
    if price_to is not None:
        out["price_to"] = price_to
    if status_filter:
        out["status_filter"] = status_filter
    if procedure_type:
        out["procedure_type"] = procedure_type
    if deadline_from:
        out["deadline_from"] = deadline_from
    if deadline_to:
        out["deadline_to"] = deadline_to
    return out


def _cursor_matches_request(
    cursor_payload: dict[str, Any],
    *,
    query: str,
    filters: dict[str, Any],
) -> bool:
    """Only resume a cursor for the exact search that created it."""
    return cursor_payload.get("q") == query and cursor_payload.get("f") == filters


def _diagnostics_dir() -> Path:
    configured = os.environ.get("AI_CORP_ZAKUPKI_SOAP_DIAGNOSTICS_DIR")
    if configured:
        return Path(configured)
    new_default = Path("company_agent_runs/zakupki_soap_diagnostics")
    old_default = Path("company_agent_runs/zakupki_soap_live_diagnostics")
    return new_default if new_default.exists() or not old_default.exists() else old_default


def _load_zakupki_live_diagnostics() -> dict[str, object]:
    status_path = _diagnostics_dir() / "last_status.json"
    if status_path.is_file():
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            return {
                "endpoint_host": payload.get("endpoint_host", ""),
                "endpoint_path": payload.get("endpoint_path", ""),
                "last_status": payload.get("last_status", ""),
                "last_error": payload.get("last_error", ""),
                "soap_action": payload.get("soap_action", ""),
                "method_name": payload.get("method_name", ""),
                "token_owner": payload.get("token_owner", ""),
                "mode": payload.get("mode", ""),
            }
        except Exception:
            return {}
    return {}


def list_procurement_sources() -> list[ProcurementSourceStatus]:
    zakupki_settings = get_zakupki_soap_settings()
    zakupki_status = zakupki_settings.safe_status()
    parsed = urlparse(zakupki_settings.active_docs_endpoint)
    live_diagnostics = _load_zakupki_live_diagnostics()
    getdocs_reason = zakupki_status["reason"] or "Токен физлица найден. getDocsIP настроен для read-only получения документации."
    return [
        ProcurementSourceStatus(
            source="demo_local",
            label="Демо-набор (локальный)",
            enabled=True,
            configured=True,
            reason=None,
            safe_diagnostics={"mode": "offline_demo"},
        ),
        ProcurementSourceStatus(
            source="public_eis_html_44fz",
            label="Публичный поиск ЕИС 44-ФЗ",
            enabled=True,
            configured=True,
            reason="Публичный read-only поиск ЕИС без авторизации.",
            safe_diagnostics={
                "mode": "public_html_read_only",
                "law": "44fz",
                "auth_required": False,
                "endpoint_host": "zakupki.gov.ru",
                "endpoint_path": "/epz/order/extendedsearch/results.html",
                "last_status": "ready",
            },
        ),
        ProcurementSourceStatus(
            source="public_eis_html_223fz",
            label="Публичный поиск ЕИС 223-ФЗ",
            enabled=True,
            configured=True,
            reason="Публичный HTML fallback. Документация и карточка закупки берутся напрямую из ЕИС в read-only режиме.",
            safe_diagnostics={"mode": "public_html_fallback", "law": "223fz"},
        ),
        ProcurementSourceStatus(
            source="public_eis_html_capital_repair",
            label="Публичный поиск ЕИС Капремонт",
            enabled=True,
            configured=True,
            reason="Публичный HTML fallback. Документация и карточка закупки берутся напрямую из ЕИС в read-only режиме.",
            safe_diagnostics={"mode": "public_html_fallback", "law": "capital_repair"},
        ),
        ProcurementSourceStatus(
            source="zakupki_gov_ru_getdocs_ip",
            label="zakupki_gov_ru_getdocs_ip",
            enabled=zakupki_settings.enabled,
            configured=zakupki_settings.configured,
            reason=getdocs_reason,
            safe_diagnostics={
                **zakupki_status,
                "token_present": zakupki_settings.token_configured,
                "endpoint_host": parsed.hostname or "",
                "endpoint_path": parsed.path or "/",
                **live_diagnostics,
            },
        ),
    ]


def _matches_text(record: DemoProcurementRecord, query: str) -> bool:
    if not query.strip():
        return True
    haystack = " ".join(
        [
            record.title,
            record.category,
            record.customer_name,
            record.procurement_number,
            record.summary,
            record.region,
        ]
    ).lower()
    return all(token in haystack for token in query.lower().split())


def _matches_optional(value: str | None, query: str | None) -> bool:
    if not query:
        return True
    return query.lower() in (value or "").lower()


def _matches_price(record: DemoProcurementRecord, price_from: float | None, price_to: float | None) -> bool:
    if record.initial_price is None:
        return price_from is None
    if price_from is not None and record.initial_price < price_from:
        return False
    if price_to is not None and record.initial_price > price_to:
        return False
    return True


def _matches_date(value: str | None, date_from: str | None, date_to: str | None) -> bool:
    if not value:
        return True
    if date_from and value < date_from:
        return False
    if date_to and value > date_to:
        return False
    return True


def _to_result(record: DemoProcurementRecord) -> ProcurementSearchResult:
    return ProcurementSearchResult(
        procurement_id=record.procurement_id,
        source=record.source,
        title=record.title,
        procurement_number=record.procurement_number,
        customer_name=record.customer_name,
        category=record.category,
        publication_date=record.publication_date,
        deadline=record.deadline,
        initial_price=record.initial_price,
        currency=record.currency,
        region=record.region,
        source_url=record.source_url,
        attachments_status=record.attachments_status,
        attachments_count=len(record.attachments),
        available_attachments_count=len(record.attachments),
        summary=record.summary,
        attachment_names=[item.name for item in record.attachments],
        source_note=record.source_note,
    )


def _to_search_result_v2(record: DemoProcurementRecord) -> ProcurementSearchResultV2:
    can_download = bool(record.attachments)
    return ProcurementSearchResultV2(
        procurement_id=record.procurement_id,
        notice_number=record.procurement_number,
        registry_number=record.procurement_number,
        title=record.title,
        customer_name=record.customer_name,
        customer_inn=None,
        law="44-ФЗ",
        source=record.source,
        source_url=record.source_url,
        publication_date=record.publication_date,
        deadline=record.deadline,
        initial_price=record.initial_price,
        currency=record.currency,
        status="demo",
        attachments_count=len(record.attachments),
        attachments_status=record.attachments_status,
        can_download_attachments=can_download,
        requires_manual_upload=not can_download,
        warnings=[] if can_download else ["Автоматическое получение документации недоступно в demo_local."],
    )


def _public_source_from_law(law: str) -> str:
    normalized = normalize_public_eis_law(law)
    if normalized == "223fz":
        return "public_eis_html_223fz"
    if normalized == "capital_repair":
        return "public_eis_html_capital_repair"
    return "public_eis_html_44fz"


def _public_law_label(law: str) -> str:
    normalized = normalize_public_eis_law(law)
    if normalized == "223fz":
        return "223-ФЗ"
    if normalized == "capital_repair":
        return "Капремонт"
    return "44-ФЗ"


def _search_demo_local_v2(request: ProcurementSearchRequestV2) -> list[ProcurementSearchResultV2]:
    records: list[ProcurementSearchResultV2] = []
    for item in get_demo_local_procurements():
        if not _matches_text(item, request.query):
            continue
        if not _matches_optional(item.customer_name, request.customer_name):
            continue
        if request.customer_inn:
            continue
        if request.law and request.law not in {"Все", "44-ФЗ"}:
            continue
        if not _matches_optional(item.region, request.region):
            continue
        if not _matches_price(item, request.price_from, request.price_to):
            continue
        if not _matches_date(item.publication_date, request.date_from, request.date_to):
            continue
        records.append(_to_search_result_v2(item))
    return records[: request.max_results]


def search_procurements(
    request: ProcurementSearchRequestV2 | None = None,
    *,
    query: str = "",
    source: str = "demo_local",
    max_results: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    customer_name: str | None = None,
    region: str | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
) -> ProcurementSearchResponse | list[ProcurementSearchResultV2]:
    if request is not None:
        sources = {item.source: item for item in list_procurement_sources()}
        if request.source not in sources:
            raise ValueError(f"Unknown procurement source: {request.source}")
        if request.source == "demo_local":
            return _search_demo_local_v2(request)
        source_status = sources[request.source]
        if not source_status.configured:
            raise RuntimeError(source_status.reason or "Источник поиска не настроен.")
        if request.source == "zakupki_gov_ru_getdocs_ip":
            raise RuntimeError("Источник ЕИС getDocsIP не поддерживает keyword search. Используйте поиск ЕИС или поиск по номеру закупки.")
        if request.source in {
            "public_eis_html_44fz",
            "public_eis_html_223fz",
            "public_eis_html_capital_repair",
        }:
            raise RuntimeError("Прямой JSON keyword search для публичного HTML-источника не реализован. Используйте endpoint public-44fz-search.")
        raise RuntimeError("Выбранный режим поиска не поддерживается.")

    descriptors = get_procurement_source_descriptors()
    allowed_sources = {item.code: item for item in descriptors}
    if source not in allowed_sources:
        raise ValueError(f"Unknown procurement source: {source}")
    if not allowed_sources[source].enabled:
        return ProcurementSearchResponse(
            query=query,
            source=source,
            results=[],
            sources=descriptors,
            warnings=[allowed_sources[source].note or "Источник временно недоступен в demo-контуре."],
        )
    if source != "demo_local":
        return ProcurementSearchResponse(
            query=query,
            source=source,
            results=[],
            sources=descriptors,
            warnings=[allowed_sources[source].note or "Поиск выполняется вручную через публичный HTML fallback."],
        )

    records = []
    for item in get_demo_local_procurements():
        if not _matches_text(item, query):
            continue
        if not _matches_optional(item.customer_name, customer_name):
            continue
        if not _matches_optional(item.region, region):
            continue
        if not _matches_price(item, price_from, price_to):
            continue
        if not _matches_date(item.publication_date, date_from, date_to):
            continue
        records.append(_to_result(item))

    return ProcurementSearchResponse(
        query=query,
        source=source,
        results=records[: max(1, min(max_results, 20))],
        sources=descriptors,
        warnings=[],
    )


_current_supplier_profile: SupplierProfile | None = None


def get_supplier_profile() -> SupplierProfile:
    global _current_supplier_profile
    if _current_supplier_profile is None:
        _current_supplier_profile = SupplierProfile.load_demo_fixture()
    return _current_supplier_profile


def reset_supplier_profile() -> SupplierProfile:
    global _current_supplier_profile
    _current_supplier_profile = SupplierProfile.load_demo_fixture()
    return _current_supplier_profile


def set_supplier_profile(profile: SupplierProfile) -> None:
    global _current_supplier_profile
    _current_supplier_profile = profile


def _normalize_public_search_query(query: str) -> str:
    """Normalize operator shorthand without weakening the requested meaning.

    EIS morphology handles Russian inflection reasonably well, but the common
    operator abbreviation ПО is otherwise treated too loosely. Expand only
    the uppercase standalone abbreviation; lowercase по remains a preposition.
    """
    cleaned = re.sub(r"\s+", " ", str(query or "")).strip()
    return re.sub(r"(?<![0-9A-Za-zА-Яа-яЁё])ПО(?![0-9A-Za-zА-Яа-яЁё])", "программного обеспечения", cleaned)


def _public_query_terms(query: str) -> list[str]:
    normalized = _normalize_public_search_query(query).lower()
    return [token for token in re.findall(r"[0-9a-zа-яё]+", normalized) if len(token) >= 4]


def _query_term_matches_title(term: str, title_tokens: list[str]) -> bool:
    if term in title_tokens:
        return True
    for token in title_tokens:
        if min(len(term), len(token)) >= 5 and (token.startswith(term) or term.startswith(token)):
            return True
        prefix = 6 if min(len(term), len(token)) >= 6 else 5
        if min(len(term), len(token)) >= prefix and term[:prefix] == token[:prefix]:
            return True
    return False


def score_public_query_match(query: str, title: str) -> dict[str, Any]:
    terms = _public_query_terms(query)
    title_tokens = re.findall(r"[0-9a-zа-яё]+", str(title or "").lower())
    if not terms:
        return {
            "score": 0.0,
            "status": "unknown",
            "matched_terms": 0,
            "total_terms": 0,
            "reasons": ["Поисковый запрос не содержит значимых терминов."],
        }
    matched = [term for term in terms if _query_term_matches_title(term, title_tokens)]
    score = round(100.0 * len(matched) / len(terms), 1)
    status = "high" if score == 100.0 else "medium" if score >= 66.0 else "low" if score > 0 else "no_match"
    return {
        "score": score,
        "status": status,
        "matched_terms": len(matched),
        "total_terms": len(terms),
        "matched": matched,
        "reasons": [f"Совпало терминов запроса: {len(matched)} из {len(terms)}."],
    }


def _matches_public_card_query(title: str | None, query: str | None) -> bool:
    if not query:
        return True
    result = score_public_query_match(query, title or "")
    if result["total_terms"] >= 2:
        return result["matched_terms"] == result["total_terms"]
    return result["matched_terms"] > 0


def _should_apply_strict_query_filter(original_query: str, effective_query: str) -> bool:
    original = str(original_query or "").strip()
    lowered = original.lower()
    # EIS itself remains authoritative for ordinary free-text discovery. The
    # strict AND boundary is only for the confirmed software-search failure
    # family where ПО or truncated "программн обеспеч" was broadened into
    # unrelated generic "разработка" cards.
    return (
        original != effective_query
        or ("програм" in lowered and "обеспеч" in lowered)
    )


def _looks_like_exact_procurement_number(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or ""))
    return bool(re.fullmatch(r"\d{11,20}", normalized))


def search_public_44fz(
    query: str,
    law: str = "44fz",
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    status_filter: str | None = None,
    procedure_type: str | None = None,
    page: int = 1,
    page_size: int = 10,
    max_results: int = 10,
    cursor: str | None = None,
    seen_registry_numbers: list[str] | None = None,
    reference_date: date | None = None,
) -> dict:
    normalized_law = normalize_public_eis_law(law)
    effective_query = _normalize_public_search_query(query)
    exact_procurement_number = _looks_like_exact_procurement_number(query)
    strict_query = (
        effective_query
        if not exact_procurement_number and _should_apply_strict_query_filter(query, effective_query)
        else None
    )
    page_num = max(page, 1)
    effective_page_size = min(max(page_size, 1), 50)
    requested_limit = min(max(max_results or effective_page_size, 1), 100)
    physical_eis_page_size = DEFAULT_SEARCH_PAGE_SIZE

    status_filter_stage_flag = resolve_public_eis_stage_flag(status_filter)
    local_status_filter = status_filter if status_filter_stage_flag is None else None
    has_non_native_filter = any([region, deadline_from, deadline_to, local_status_filter, procedure_type])

    cursor_filters = _build_cursor_filters(
        region=region,
        date_from=date_from,
        date_to=date_to,
        price_from=price_from,
        price_to=price_to,
        status_filter=status_filter,
        procedure_type=procedure_type,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        law=normalized_law,
    )

    seen: set[str] = set((seen_registry_numbers or []))
    start_eis_page = page_num
    next_eis_page = page_num

    if cursor:
        decoded = _decode_search_cursor(cursor)
        if not decoded or not _cursor_matches_request(decoded, query=query, filters=cursor_filters):
            raise ValueError("Cursor не соответствует текущему поисковому запросу и фильтрам.")
        start_eis_page = decoded.get("ep", 1)
        next_eis_page = start_eis_page
        seen = set(decoded.get("sn", []))
        page_num = decoded.get("up", 1) + 1

    try:
        first_url = build_public_eis_search_url(
            query=effective_query,
            law=normalized_law,
            region=region,
            date_from=date_from,
            date_to=date_to,
            price_from=price_from,
            price_to=price_to,
            status_filter=status_filter,
            page=next_eis_page,
            max_results=physical_eis_page_size,
        )
    except ValueError as exc:
        return PublicProcurementSearchResponse(
            status="validation_error",
            outcome=ProcurementSearchOutcome.VALIDATION_ERROR,
            query=query,
            source=_public_source_from_law(normalized_law),
            page=page_num,
            page_size=effective_page_size,
            returned_count=0,
            total_count=None,
            total_count_source=None,
            total_count_exact_for_displayed_filters=False,
            raw_returned_count=None,
            local_filtered_count=0,
            local_post_filter_applied=False,
            eis_pages_fetched=0,
            has_more=False,
            next_page=None,
            next_cursor=None,
            requested_limit=requested_limit,
            sort="publication_date_desc",
            cards=[],
            eis_search_url=None,
            error=str(exc),
            parser_status=Public44FzSearchStatus.MANUAL_OPEN_REQUIRED,
            message="Поисковый запрос не прошёл валидацию. Исправьте параметры и повторите поиск.",
            warnings=[],
        ).model_dump(mode="json")

    first_fetch_url = first_url

    def _build_error_response(status_val, outcome_val, msg, err=None, ps=None, url=first_fetch_url):
        return PublicProcurementSearchResponse(
            status=status_val,
            outcome=outcome_val,
            query=query,
            source=_public_source_from_law(normalized_law),
            page=page_num,
            page_size=effective_page_size,
            returned_count=0,
            total_count=None,
            total_count_source=None,
            total_count_exact_for_displayed_filters=False,
            raw_returned_count=None,
            local_filtered_count=0,
            local_post_filter_applied=False,
            eis_pages_fetched=1 if ps else 0,
            has_more=False,
            next_page=None,
            next_cursor=None,
            requested_limit=requested_limit,
            sort="publication_date_desc",
            cards=[],
            eis_search_url=url,
            error=err,
            parser_status=ps or status_val,
            message=msg,
            warnings=[],
        ).model_dump(mode="json")

    fetch_result = fetch_public_44fz_search_page(first_fetch_url)
    parser_status = fetch_result.get("status", Public44FzSearchStatus.NETWORK_ERROR)

    if parser_status == Public44FzSearchStatus.EMPTY_RESULTS:
        return _build_error_response(
            parser_status, ProcurementSearchOutcome.SUCCESS_EMPTY,
            "Источник доступен, но по заданным фильтрам закупки не найдены.",
            ps=parser_status,
        )

    if parser_status != Public44FzSearchStatus.PARSED or not fetch_result.get("html"):
        error_message = fetch_result.get("error")
        outcome = ProcurementSearchOutcome.SOURCE_ERROR
        message = "Поиск ЕИС завершился с ошибкой обработки ответа."
        if parser_status in {
            Public44FzSearchStatus.NETWORK_ERROR,
            Public44FzSearchStatus.TIMEOUT,
            Public44FzSearchStatus.BAD_GATEWAY,
            Public44FzSearchStatus.BLOCKED,
            Public44FzSearchStatus.CAPTCHA,
            Public44FzSearchStatus.CAPTCHA_OR_BLOCKED,
            Public44FzSearchStatus.JS_HEAVY,
        }:
            outcome = ProcurementSearchOutcome.SOURCE_UNAVAILABLE
            message = "Публичный поиск ЕИС сейчас недоступен для автоматического чтения. Откройте выдачу в ЕИС или используйте демо-закупку."
        elif parser_status == Public44FzSearchStatus.MANUAL_OPEN_REQUIRED:
            outcome = ProcurementSearchOutcome.UNSUPPORTED_SEARCH_MODE
            message = "Этот режим поиска не поддерживается автоматически. Откройте поиск в ЕИС вручную."
        return _build_error_response(parser_status, outcome, message, err=error_message, ps=parser_status)

    parsed_total_count = extract_public_search_total_count(fetch_result["html"])
    total_count_source: str | None = None
    if parsed_total_count is not None:
        total_count_source = "eis_download_csv"

    has_eis_total = parsed_total_count is not None

    valid_cards: list[dict] = []
    total_raw_count = 0
    total_filtered_count = 0
    pages_fetched = 0
    eis_has_more = True
    current_eis_page = next_eis_page

    while len(valid_cards) < requested_limit and pages_fetched < MAX_BACKFILL_PAGES and eis_has_more:
        if pages_fetched == 0 and not cursor:
            fetch_url = first_fetch_url
            raw_html = fetch_result.get("html", "")
        else:
            fetch_url = build_public_eis_search_url(
                query=effective_query,
                law=normalized_law,
                region=region,
                date_from=date_from,
                date_to=date_to,
                price_from=price_from,
                price_to=price_to,
                status_filter=status_filter,
                page=current_eis_page,
                max_results=physical_eis_page_size,
            )
            page_fetch = fetch_public_44fz_search_page(fetch_url)
            if page_fetch.get("status") != Public44FzSearchStatus.PARSED or not page_fetch.get("html"):
                break
            raw_html = page_fetch.get("html", "")

        page_cards = parse_44fz_search_results(raw_html)
        if not page_cards:
            eis_has_more = False
            break

        total_raw_count += len(page_cards)

        filtered = _filter_public_44fz_cards(
            page_cards,
            query=strict_query,
            date_from=date_from,
            date_to=date_to,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            price_from=price_from,
            price_to=price_to,
            status_filter=local_status_filter,
            procedure_type=procedure_type,
            status_grace_days=2,
            reference_date=reference_date,
            skip_status_consistency=exact_procurement_number,
        )
        newly_filtered = len(page_cards) - len(filtered)
        total_filtered_count += newly_filtered

        for card in filtered:
            reg_num = card.get("reestr_number") or card.get("notice_number") or ""
            if reg_num and reg_num in seen:
                continue
            if reg_num:
                seen.add(reg_num)
            valid_cards.append(card)

        pages_fetched += 1
        current_eis_page += 1

        if len(page_cards) < physical_eis_page_size and not has_eis_total:
            eis_has_more = False

    is_backfill = pages_fetched > 1

    if not valid_cards:
        return PublicProcurementSearchResponse(
            status=Public44FzSearchStatus.EMPTY_RESULTS,
            outcome=ProcurementSearchOutcome.SUCCESS_EMPTY,
            query=query,
            source=_public_source_from_law(normalized_law),
            page=page_num,
            page_size=effective_page_size,
            returned_count=0,
            total_count=parsed_total_count,
            total_count_source=total_count_source,
            total_count_exact_for_displayed_filters=False,
            raw_returned_count=total_raw_count,
            local_filtered_count=total_filtered_count,
            local_post_filter_applied=True,
            eis_pages_fetched=pages_fetched,
            has_more=False,
            next_page=None,
            next_cursor=None,
            requested_limit=requested_limit,
            sort="publication_date_desc",
            cards=[],
            eis_search_url=first_fetch_url,
            error=None,
            parser_status=Public44FzSearchStatus.PARSED,
            message="Источник доступен, но после применения фильтров закупки не найдены.",
            warnings=[],
        ).model_dump(mode="json")

    valid_cards = _sort_public_44fz_cards(valid_cards)
    valid_cards = _enrich_public_search_cards(valid_cards, max_enrichments=min(requested_limit, 5))
    profile = None if exact_procurement_number else get_supplier_profile()
    scored_cards = []
    for card in valid_cards[:requested_limit]:
        card_with_relevance = dict(card)
        card_with_relevance["law"] = normalized_law
        card_with_relevance["category"] = _public_law_label(normalized_law)
        card_with_relevance["source"] = _public_source_from_law(normalized_law)
        card_with_relevance["query_relevance"] = score_public_query_match(
            query, card.get("title", "")
        )
        if profile is not None:
            result = score_procurement_card(
                title=card.get("title", ""),
                initial_price=card.get("initial_price"),
                customer_name=card.get("customer_name"),
                submission_deadline=card.get("deadline"),
                profile=profile,
            )
            card_with_relevance["supplier_fit"] = result.to_dict()
            card_with_relevance["relevance"] = result.to_dict()
        scored_cards.append(card_with_relevance)

    returned_count = len(scored_cards)
    local_post_filter_applied = total_filtered_count > 0

    total_count_exact_for_displayed_filters = False
    if has_eis_total:
        if not has_non_native_filter and not local_post_filter_applied:
            total_count_exact_for_displayed_filters = True

    eis_has_more_results = eis_has_more

    has_more = False
    if total_count_exact_for_displayed_filters and has_eis_total:
        has_more = len(seen) < parsed_total_count
    elif eis_has_more_results:
        has_more = True
    elif not is_backfill and len(valid_cards) > effective_page_size:
        has_more = True
    elif is_backfill and (
        eis_has_more_results or current_eis_page <= page_num + MAX_BACKFILL_PAGES
    ):
        has_more = True

    next_cursor_val: str | None = None
    if has_more:
        next_cursor_val = _encode_search_cursor(
            query=query,
            filters=cursor_filters,
            next_eis_page=current_eis_page,
            seen_registry_numbers=sorted(seen),
            page_size=effective_page_size,
            ui_page=page_num,
        )

    summary_message = _build_search_message(
        page_num=page_num,
        page_size=effective_page_size,
        returned_count=returned_count,
        total_count=parsed_total_count,
        total_count_exact=total_count_exact_for_displayed_filters,
        has_more=has_more,
        has_non_native_filter=has_non_native_filter,
        local_post_filter_applied=local_post_filter_applied,
    )

    return PublicProcurementSearchResponse(
        status=Public44FzSearchStatus.PARSED,
        outcome=ProcurementSearchOutcome.SUCCESS_WITH_RESULTS,
        query=query,
        source=_public_source_from_law(normalized_law),
        page=page_num,
        page_size=effective_page_size,
        returned_count=returned_count,
        total_count=parsed_total_count,
        total_count_source=total_count_source,
        total_count_exact_for_displayed_filters=total_count_exact_for_displayed_filters,
        raw_returned_count=total_raw_count,
        local_filtered_count=total_filtered_count,
        local_post_filter_applied=local_post_filter_applied,
        eis_pages_fetched=pages_fetched,
        has_more=has_more,
        next_page=None,
        next_cursor=next_cursor_val,
        requested_limit=requested_limit,
        sort="publication_date_desc",
        cards=scored_cards,
        eis_search_url=first_fetch_url,
        error=None,
        parser_status=Public44FzSearchStatus.PARSED,
        message=summary_message,
        warnings=[],
    ).model_dump(mode="json")


def _build_search_message(
    *,
    page_num: int,
    page_size: int,
    returned_count: int,
    total_count: int | None,
    total_count_exact: bool,
    has_more: bool,
    has_non_native_filter: bool,
    local_post_filter_applied: bool,
) -> str:
    if returned_count == 0:
        return "Источник доступен, но после применения фильтров закупки не найдены."

    if total_count_exact and total_count is not None:
        if page_num == 1 or page_num is None:
            return f"Показаны первые {returned_count} карточек из {total_count}."
        if page_num == 2:
            return f"Показаны следующие {returned_count} карточек из {total_count}."
        return f"Показаны карточки (страница {page_num}) из {total_count}."

    if total_count is not None and not total_count_exact:
        if has_non_native_filter:
            return (
                f"По данным ЕИС найдено {total_count}. "
                f"Показаны первые {returned_count} карточек после уточнения."
            )
        if local_post_filter_applied:
            return (
                f"По данным ЕИС найдено {total_count}. "
                f"Показаны первые {returned_count} актуальных карточек после проверки."
            )
        if page_num == 1 or page_num is None:
            return f"Показаны первые {returned_count} карточек из {total_count}."
        return f"Показаны следующие карточки. Всего найдено: {total_count}."

    if returned_count < page_size:
        if has_more:
            return f"Показаны {returned_count} карточек. Есть ещё результаты."
        return f"Показаны {returned_count} карточек. Больше результатов не найдено."

    if page_num == 1 or page_num is None:
        if has_more:
            if local_post_filter_applied:
                return f"Показаны первые {returned_count} актуальных карточек. Есть ещё результаты."
            return f"Показаны первые {returned_count} карточек. Есть ещё результаты."
        return f"Показаны первые {returned_count} карточек."

    if has_more:
        return f"Показаны следующие {returned_count} карточек. Есть ещё результаты."
    return f"Показаны следующие {returned_count} карточек."


def _parse_public_card_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _enrich_public_search_cards(cards: list[dict], *, max_enrichments: int = 5) -> list[dict]:
    """Fill missing identity/deadline from the authoritative public detail page.

    Search-card HTML is intentionally treated as untrusted for customer identity.
    Only cards with missing fields are enriched, and the number of detail fetches
    is capped so ordinary discovery remains responsive.
    """
    provider = Public44FzSearchProvider(timeout_seconds=10, bypass_proxy=True)
    enriched: list[dict] = []
    enrichments = 0
    for original in cards:
        card = dict(original)
        deadline_text = str(card.get("deadline") or "").strip()
        needs_deadline_detail = not re.search(r"\b\d{2}:\d{2}\b", deadline_text)
        needs_detail = not card.get("customer_name") or needs_deadline_detail
        registry_number = card.get("reestr_number") or card.get("notice_number")
        source_url = card.get("source_url") or card.get("card_url")
        if needs_detail and registry_number and source_url and enrichments < max_enrichments:
            enrichments += 1
            try:
                detail = provider.fetch_detail(
                    registry_number=str(registry_number),
                    card_url=str(source_url),
                )
                if detail.network_status == "success":
                    if not card.get("customer_name") and detail.customer_name:
                        card["customer_name"] = detail.customer_name
                        card["customer_identity_source"] = "eis_common_info"
                    if needs_deadline_detail and detail.application_deadline:
                        detail_metadata = (
                            detail.raw.get("detail_metadata", {})
                            if isinstance(detail.raw, dict)
                            else {}
                        )
                        source_deadline = str(
                            detail_metadata.get("application_deadline_source_text") or ""
                        ).strip()
                        card["deadline"] = (
                            source_deadline
                            or detail.application_deadline.strftime("%d.%m.%Y %H:%M")
                        )
                        card["deadline_utc"] = detail.application_deadline.isoformat()
                        card["deadline_source"] = "eis_common_info"
            except Exception:
                # Discovery stays fail-closed: missing identity remains missing.
                pass
        enriched.append(card)
    return enriched


def _sort_public_44fz_cards(cards: list[dict]) -> list[dict]:
    def sort_key(card: dict) -> tuple[int, int]:
        parsed_date = _parse_public_card_date(card.get("publication_date"))
        if parsed_date is None:
            return (1, 0)
        return (0, -parsed_date.toordinal())

    return sorted(cards, key=sort_key)


def _matches_public_card_date_range(value: str | None, date_from: str | None, date_to: str | None) -> bool:
    parsed_value = _parse_public_card_date(value)
    if parsed_value is None:
        return True
    parsed_from = _parse_public_card_date(date_from)
    parsed_to = _parse_public_card_date(date_to)
    if parsed_from and parsed_value < parsed_from:
        return False
    if parsed_to and parsed_value > parsed_to:
        return False
    return True


def _matches_public_card_text(value: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    haystack = (value or "").strip().lower()
    needle = expected.strip().lower()
    return needle in haystack


def _matches_public_card_status_consistency(card: dict, *, today: date | None = None, grace_days: int = 0) -> bool:
    status = (card.get("status") or "").strip().lower()
    if "подача заявок" not in status:
        return True
    parsed_deadline = _parse_public_card_date(card.get("deadline"))
    if parsed_deadline is None:
        return True
    current_day = today or date.today()
    return parsed_deadline >= current_day - timedelta(days=grace_days)


def _filter_public_44fz_cards(
    cards: list[dict],
    *,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
    status_filter: str | None = None,
    procedure_type: str | None = None,
    status_grace_days: int = 0,
    reference_date: date | None = None,
    skip_status_consistency: bool = False,
) -> list[dict]:
    filtered: list[dict] = []
    effective_status_grace_days = status_grace_days or (2 if status_filter else 0)
    for card in cards:
        if not _matches_public_card_query(card.get("title"), query):
            continue
        # Explicit deadline ranges are authoritative. Otherwise retain the
        # normal active-status expiry check, with the caller-selected grace
        # period (the search path uses a small ingestion grace window).
        if not skip_status_consistency and not (deadline_from or deadline_to) and not _matches_public_card_status_consistency(
            card, today=reference_date, grace_days=effective_status_grace_days
        ):
            continue
        if not _matches_public_card_date_range(card.get("publication_date"), date_from, date_to):
            continue
        if not _matches_public_card_date_range(card.get("deadline"), deadline_from, deadline_to):
            continue
        if price_from is not None and card.get("initial_price") is not None and card["initial_price"] < price_from:
            continue
        if price_to is not None and card.get("initial_price") is not None and card["initial_price"] > price_to:
            continue
        if not _matches_public_card_text(card.get("status"), status_filter):
            continue
        if not _matches_public_card_text(card.get("procedure_type"), procedure_type):
            continue
        filtered.append(card)
    return filtered


def build_public_search_url(
    *,
    query: str,
    law: str,
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> PublicSearchUrlResponse:
    normalized_law = normalize_public_eis_law(law)
    return PublicSearchUrlResponse(
        source=_public_source_from_law(normalized_law),
        law=normalized_law,
        query=query,
        eis_search_url=build_public_eis_search_url(
            query=query,
            law=normalized_law,
            region=region,
            date_from=date_from,
            date_to=date_to,
        ),
        note="Откройте карточку закупки в ЕИС, затем запустите обработку прямо из результата поиска или по ссылке.",
    )


def get_demo_procurement(source: str, procurement_id: str) -> DemoProcurementRecord | None:
    if source != "demo_local":
        return None
    for item in get_demo_local_procurements():
        if item.procurement_id == procurement_id:
            return item
    return None


def get_procurement_details(source: str, procurement_id: str) -> ProcurementDetails:
    sources = {item.source for item in list_procurement_sources()}
    if source not in sources:
        raise ValueError(f"Unknown procurement source: {source}")
    if source == "zakupki_gov_ru_getdocs_ip":
        raise ValueError("getDocsIP не используется как поиск карточки. Сначала найдите закупку публично, затем запросите документацию по номеру.")
    if source in {"public_eis_html_44fz", "public_eis_html_223fz", "public_eis_html_capital_repair"}:
        raise ValueError("Для public HTML fallback карточка закупки открывается вручную в ЕИС.")
    record = get_demo_procurement(source, procurement_id)
    if record is None:
        raise ValueError("Procurement was not found")
    attachments = [
        ProcurementAttachment(
            attachment_id=f"{record.procurement_id}-ATT-{index:02d}",
            name=item.name,
            url=None,
            content_type=item.content_type,
            size_bytes=len(item.payload),
            extension="." + item.name.rsplit(".", 1)[-1].lower() if "." in item.name else None,
            can_download=True,
            requires_manual_upload=False,
        )
        for index, item in enumerate(record.attachments, start=1)
    ]
    return ProcurementDetails(
        procurement=_to_search_result_v2(record),
        attachments=attachments,
        raw_source_summary=record.summary,
        warnings=[],
    )
