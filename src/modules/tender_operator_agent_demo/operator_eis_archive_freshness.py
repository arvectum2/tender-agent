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


def needs_live_eis_revision_review(metadata: dict[str, Any]) -> bool:
    if metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip":
        return False
    if metadata.get("notice_revision_requires_review") is True:
        return True
    revision = metadata.get("notice_revision_selected")
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
    if not needs_live_eis_revision_review(metadata):
        return report
    projected = copy.deepcopy(report)
    projected["recommendation"] = "manual_review_required"
    projected["recommendation_label"] = EIS_ARCHIVE_REVIEW_LABEL
    projected["manual_checks"] = append_once(
        projected.get("manual_checks"), EIS_ARCHIVE_REVIEW_MESSAGE
    )
    projected["executive_summary"] = append_once(
        projected.get("executive_summary"), EIS_ARCHIVE_REVIEW_MESSAGE
    )
    markdown = str(projected.get("report_markdown") or "")
    if not markdown.startswith(EIS_ARCHIVE_REVIEW_MESSAGE):
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
    if not needs_live_eis_revision_review(metadata):
        return html_document
    marker = 'data-arvectum-eis-archive-review="required"'
    if marker in html_document:
        return html_document
    banner = (
        f'<aside {marker} role="alert" '
        'style="padding:18px;border:3px solid #b45309;'
        'background:#fff7ed;color:#7c2d12;font-weight:700">'
        + EIS_ARCHIVE_REVIEW_MESSAGE + "</aside>"
    )
    body = re.search(r"<body(?:\s[^>]*)?>", html_document, flags=re.IGNORECASE)
    if body:
        return html_document[:body.end()] + banner + html_document[body.end():]
    return banner + html_document


def projected_historical_eis_run(metadata: dict[str, Any], response: Any) -> Any:
    """Pydantic model copy; original data and persisted outputs remain untouched."""
    if not needs_live_eis_revision_review(metadata):
        return response
    return response.model_copy(
        update={
            "limitations": append_once(
                response.limitations, EIS_ARCHIVE_REVIEW_MESSAGE
            ),
            "warnings": append_once(
                response.warnings, EIS_ARCHIVE_REVIEW_MESSAGE
            ),
            "final_recommendation": None,
            "human_in_the_loop": True,
            "external_actions": False,
        }
    )


def reject_unsafe_historical_eis_binary_export(metadata: dict[str, Any]) -> None:
    """Stop canonical PDF/DOCX from bypassing read-time review projections."""
    if not needs_live_eis_revision_review(metadata):
        return
    from fastapi import HTTPException

    raise HTTPException(
        status_code=409,
        detail=EIS_ARCHIVE_REVIEW_MESSAGE,
    )
