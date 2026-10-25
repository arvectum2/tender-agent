"""Pure HTML presentation helpers for historical operator reports.

No procurement facts or source authority are inferred from these formatters.
The original nested helper bodies are extracted without logical changes.
"""
from __future__ import annotations

import html
from typing import Any


def list_html(items: list[str]) -> str:
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"не указан", "none", "null", "n/a", "—"}


def format_value(value: Any, *, fallback: str = "не указано") -> str:
    return fallback if is_missing(value) else str(value).strip()


def format_date_ru(value: Any) -> str:
    text = str(value).strip() if value else ""
    import re
    iso_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        return f"{iso_match.group(3)}.{iso_match.group(2)}.{iso_match.group(1)}"
    rus_match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if rus_match:
        return text
    return text


def format_price(amount: Any, currency: Any) -> str:
    if amount in (None, ""):
        return "не указана"
    if isinstance(amount, float):
        amount_text = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    else:
        amount_text = str(amount)
    currency_text = str(currency).strip() if currency else ""
    if not currency_text:
        currency_text = "₽"
    return f"{amount_text} {currency_text}".strip()


def build_archive_button_html(run_id: str, archive_available: bool) -> str:
    if not archive_available:
        return ""
    return (
        f'<a class="action-button primary" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/archive/download">Скачать архив</a>'
    )


def build_export_buttons_html(run_id: str) -> str:
    return (
        f'<a class="action-button" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/export/docx">Скачать DOCX</a>'
        f'<a class="action-button" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/export/pdf">Скачать PDF</a>'
    )


def build_document_list_html(run_id: str, files_payload: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for item in files_payload:
        file_id = str(item.get("file_id") or "").strip()
        display_name = format_value(item.get("display_name"), fallback="Документ")
        if not file_id:
            continue
        items.append(
            f'<li><a class="doc-link" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/files/{html.escape(file_id)}/download">{html.escape(display_name)}</a></li>'
        )
    if not items:
        return '<div class="muted">Документы для скачивания пока не доступны.</div>'
    return "".join(items)


def build_document_toggle_html(run_id: str, files_payload: list[dict[str, Any]]) -> str:
    content = build_document_list_html(run_id, files_payload)
    if content.startswith("<div"):
        return content
    return (
        '<details class="document-toggle">'
        '<summary class="action-button">Показать документы</summary>'
        f'<ul class="document-list">{content}</ul>'
        '</details>'
    )


def format_publication_update(publication_date: Any, updated_date: Any) -> str:
    publication = format_value(publication_date)
    updated = format_value(updated_date, fallback="")
    if updated and updated != publication:
        return f"{publication} / {updated}"
    return publication


def render_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>Нет данных для отображения.</p>"
    header_html = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
