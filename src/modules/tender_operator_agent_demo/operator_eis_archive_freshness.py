"""Read-only fail-closed projection for reports built from archived EIS notices.

An archived getDocsIP snapshot is never proof of the *current* EIS revision.
Do not rewrite historical reports: projected API/HTML must instead make a
historically stored GO/non-GO unusable as an approved present-day decision.
"""
from __future__ import annotations

import copy
import re
from typing import Any

EIS_ARCHIVE_REVIEW_MESSAGE = (
    "АРХИВНОЕ ИЗВЕЩЕНИЕ ЕИС: действующая опубликованная редакция и срок "
    "подачи заявок не подтверждены. Историческое решение нельзя использовать "
    "для участия без повторной проверки официального ЕИС и нового анализа."
)
EIS_ARCHIVE_REVIEW_LABEL = "Требуется ручная проверка редакции ЕИС"

PRICE_INFORMATION_REVIEW_MESSAGE = (
    "ЗАПРОС ЦЕНОВОЙ ИНФОРМАЦИИ: официальный источник подтверждает "
    "исследование рынка, а не конкурентную процедуру подачи заявки. "
    "Рекомендация участия в торгах неприменима."
)
PRICE_INFORMATION_REVIEW_LABEL = "Не конкурентная закупка: запрос ценовой информации"


def verified_noncompetitive_price_request(metadata: dict[str, Any]) -> bool:
    """Only source-attested official evidence, never a number or SOAP no_data."""
    evidence = metadata.get("procedure_type_evidence")
    if not isinstance(evidence, dict):
        return False
    number = metadata.get("procurement_id") or metadata.get("notice_number")
    return (
        evidence.get("authority") == "eis_official"
        and evidence.get("procedure_type") == "price_information_request"
        and isinstance(number, str)
        and bool(number)
        and evidence.get("procurement_id") == number
        and isinstance(evidence.get("source_document_sha256"), str)
        and re.fullmatch(r"[a-f0-9]{64}", evidence["source_document_sha256"]) is not None
        and isinstance(evidence.get("official_source_url"), str)
        and evidence["official_source_url"].startswith("https://zakupki.gov.ru/")
    )



def needs_live_eis_revision_review(metadata: dict[str, Any]) -> bool:
    if metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip":
        return False
    if metadata.get("notice_revision_requires_review") is True:
        return True
    revision = metadata.get("notice_revision_selected")
    # Never accept a live-verification flag attached to the wrong procurement.
    # Older manually attested records may not have this optional field.
    if isinstance(revision, dict) and revision.get("purchase_number") is not None:
        actual = revision["purchase_number"]
        expected = metadata.get("procurement_id") or metadata.get("notice_number")
        if not isinstance(actual, str) or not expected or actual != str(expected):
            return True
    return not (
        isinstance(revision, dict)
        and revision.get("current_live_eis_verified") is True
    )


def append_once(values: list[str] | None, message: str) -> list[str]:
    entries = list(values or [])
    if message not in entries:
        entries.insert(0, message)
    return entries


def projected_historical_eis_report(
    metadata: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    price_request = verified_noncompetitive_price_request(metadata)
    archive_review = needs_live_eis_revision_review(metadata)
    if not price_request and not archive_review:
        return report
    projected = copy.deepcopy(report)
    projected["recommendation"] = "manual_review_required"
    projected["recommendation_label"] = (
        PRICE_INFORMATION_REVIEW_LABEL if price_request else EIS_ARCHIVE_REVIEW_LABEL
    )
    if price_request:
        projected["manual_checks"] = append_once(
            projected.get("manual_checks"), PRICE_INFORMATION_REVIEW_MESSAGE
        )
        projected["executive_summary"] = append_once(
            projected.get("executive_summary"), PRICE_INFORMATION_REVIEW_MESSAGE
        )
        markdown = str(projected.get("report_markdown") or "")
        if PRICE_INFORMATION_REVIEW_MESSAGE not in markdown:
            projected["report_markdown"] = (
                PRICE_INFORMATION_REVIEW_MESSAGE + "\n\n---\n\n" + markdown
            )
        decision = projected.get("decision_core")
        if isinstance(decision, dict):
            decision["noncompetitive_price_request"] = True
            decision["historical_decision_not_authoritative"] = True
            decision["price_request_type_source"] = "eis_official"
    if not archive_review:
        return projected
    projected["manual_checks"] = append_once(
        projected.get("manual_checks"), EIS_ARCHIVE_REVIEW_MESSAGE
    )
    projected["executive_summary"] = append_once(
        projected.get("executive_summary"), EIS_ARCHIVE_REVIEW_MESSAGE
    )
    markdown = str(projected.get("report_markdown") or "")
    if EIS_ARCHIVE_REVIEW_MESSAGE not in markdown:
        projected["report_markdown"] = (
            EIS_ARCHIVE_REVIEW_MESSAGE + "\n\n---\n\n" + markdown
        )
    decision = projected.get("decision_core")
    if isinstance(decision, dict):
        decision["historical_decision_not_authoritative"] = True
        decision["current_eis_revision_status"] = "UNKNOWN"
        unknowns = decision.get("unknowns")
        if isinstance(unknowns, list) and not any(
            isinstance(item, dict)
            and item.get("code") == "EIS_CURRENT_NOTICE_REVISION_UNVERIFIED"
            for item in unknowns
        ):
            unknowns.append(
                {
                    "code": "EIS_CURRENT_NOTICE_REVISION_UNVERIFIED",
                    "summary": EIS_ARCHIVE_REVIEW_MESSAGE,
                }
            )
    return projected


def review_annotated_html(
    metadata: dict[str, Any], html_document: str
) -> str:
    price = verified_noncompetitive_price_request(metadata)
    archive = needs_live_eis_revision_review(metadata)
    if not price and not archive:
        return html_document
    marker = (
        'data-arvectum-eis-archive-review="required"'
        if archive else 'data-arvectum-price-request-review="required"'
    )
    if marker in html_document:
        return html_document
    reasons = [
        message for active, message in (
            (archive, EIS_ARCHIVE_REVIEW_MESSAGE),
            (price, PRICE_INFORMATION_REVIEW_MESSAGE),
        ) if active
    ]
    banner = (
        f'<aside {marker} role="alert" '
        'style="padding:18px;border:3px solid #b45309;'
        'background:#fff7ed;color:#7c2d12;font-weight:700">'
        + " ".join(reasons) + "</aside>"
    )
    body = re.search(r"<body(?:\s[^>]*)?>", html_document, flags=re.IGNORECASE)
    if body:
        return html_document[:body.end()] + banner + html_document[body.end():]
    return banner + html_document


def projected_historical_eis_run(metadata: dict[str, Any], response: Any) -> Any:
    """Pydantic model copy; original data and persisted outputs remain untouched."""
    price = verified_noncompetitive_price_request(metadata)
    archive = needs_live_eis_revision_review(metadata)
    if not price and not archive:
        return response
    messages = [
        text for active, text in (
            (price, PRICE_INFORMATION_REVIEW_MESSAGE),
            (archive, EIS_ARCHIVE_REVIEW_MESSAGE),
        ) if active
    ]
    limitations = list(response.limitations or [])
    warnings = list(response.warnings or [])
    for message in messages:
        limitations = append_once(limitations, message)
        warnings = append_once(warnings, message)
    return response.model_copy(
        update={
            "limitations": limitations,
            "warnings": warnings,
            "final_recommendation": None,
            "human_in_the_loop": True,
            "external_actions": False,
        }
    )


def reject_unsafe_historical_eis_binary_export(metadata: dict[str, Any]) -> None:
    """Stop canonical PDF/DOCX from bypassing read-time review projections."""
    price = verified_noncompetitive_price_request(metadata)
    archive = needs_live_eis_revision_review(metadata)
    if not price and not archive:
        return
    from fastapi import HTTPException

    raise HTTPException(
        status_code=409,
        detail=(
            PRICE_INFORMATION_REVIEW_MESSAGE
            if price else EIS_ARCHIVE_REVIEW_MESSAGE
        ),
    )
