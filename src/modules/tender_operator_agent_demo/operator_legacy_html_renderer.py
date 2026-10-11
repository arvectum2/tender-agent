"""Historical Operator report HTML rendering isolated from upload orchestration.

The legacy callable signature remains unchanged at its original module boundary.
No authority is inferred from formatting; all values are HTML escaped as before.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any


def render_legacy_report_html(
    metadata: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
    *,
    inventory_builder: Callable[..., Any],
    supply_section_title: Callable[..., Any],
    input_dir_resolver: Callable[..., Any],
) -> str:
    from src.modules.tender_operator_agent_demo.operator_html_primitives import (
        build_archive_button_html,
        build_document_toggle_html,
        build_export_buttons_html,
        format_date_ru,
        format_price,
        format_publication_update,
        format_value,
        list_html,
        render_table,
    )

    requirements = outputs["requirements"]
    questions = outputs["supplier_questions"]
    quotes = outputs["quotes_comparison"]
    economics = outputs["economics"]
    risks = outputs["contract_risks"]
    final_recommendation = outputs["final_recommendation"]
    trace = outputs["trace"]
    preliminary_analysis = requirements.get("preliminary_analysis", {})
    downloaded_docs = inventory_builder(metadata)
    files = metadata.get("files", [])
    procurement = metadata.get("procurement", {})
    procurement_manual_required = bool(metadata.get("manual_upload_required") or metadata.get("attachments_status") == "manual_upload_required" or not files)
    procurement_url = str(metadata.get("procurement_url") or procurement.get("source_url") or "").strip()
    notice_number = format_value(metadata.get("notice_number") or metadata.get("procurement_id") or procurement.get("procurement_number"))
    notice_number_html = (
        f'<a class="inline-link" href="{html.escape(procurement_url)}" target="_blank" rel="noopener noreferrer">{html.escape(notice_number)}</a>'
        if procurement_url and notice_number != "не указано"
        else html.escape(notice_number)
    )
    publication_update = format_publication_update(
        format_date_ru(metadata.get("publication_date") or procurement.get("publication_date")),
        format_date_ru(metadata.get("updated_date") or procurement.get("updated_date")),
    )
    deadline_ru = format_date_ru(metadata.get("deadline") or procurement.get("deadline"))
    delivery_term_ru = format_date_ru(procurement.get("delivery_term"))
    downloaded_files_count = int(metadata.get("downloaded_files_count", len(files)))
    archive_available = (input_dir_resolver(str(metadata.get("run_id"))) / "documentation-archive.zip").is_file()
    archive_button_html = build_archive_button_html(str(metadata.get("run_id")), archive_available)
    document_toggle_html = build_document_toggle_html(str(metadata.get("run_id")), files)
    export_buttons_html = build_export_buttons_html(str(metadata.get("run_id")))

    from src.modules.tender_operator_agent_demo.operator_html_layout import (
        render_operator_html_layout,
    )

    return render_operator_html_layout(
        archive_button_html=archive_button_html,
        deadline_ru=deadline_ru,
        delivery_term_ru=delivery_term_ru,
        document_toggle_html=document_toggle_html,
        downloaded_docs=downloaded_docs,
        downloaded_files_count=downloaded_files_count,
        economics=economics,
        export_buttons_html=export_buttons_html,
        files=files,
        final_recommendation=final_recommendation,
        format_price=format_price,
        format_value=format_value,
        list_html=list_html,
        metadata=metadata,
        notice_number_html=notice_number_html,
        outputs=outputs,
        preliminary_analysis=preliminary_analysis,
        procurement=procurement,
        procurement_manual_required=procurement_manual_required,
        publication_update=publication_update,
        questions=questions,
        quotes=quotes,
        render_table=render_table,
        requirements=requirements,
        risks=risks,
        supply_section_title=supply_section_title,
        trace=trace,
    )
