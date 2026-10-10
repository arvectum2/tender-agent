"""Product-owned procurement metadata authority and evidence precedence.

Separate business evidence merge from the legacy upload/file-management code;
caller supplies its legacy placeholder/date functions for compatibility.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument


def enrich_procurement_metadata(
    metadata: dict[str, Any],
    *,
    documents: list[AnalyzedDocument] | None = None,
    combined_text: str | None = None,
    notice_text: str | None,
    technical_spec_text: str | None,
    contract_draft_text: str | None,
    missing_value: Callable[[Any], bool],
    updated_date_from_text: Callable[..., str | None],
) -> dict[str, Any]:
    from src.modules.tender_operator_agent_demo.eis_notice_parser import (
        apply_structured_metadata_to_procurement,
        extract_notice_metadata,
        merge_structured_metadata,
    )

    procurement = dict(metadata.get("procurement") or {})

    eis_notice_meta: dict[str, Any] = {}
    if documents:
        for doc in documents:
            if doc.role == "notice" and doc.extension == ".xml" and doc.raw_content:
                raw_text = doc.raw_content.decode("utf-8", errors="replace")
                parsed = extract_notice_metadata(raw_text)
                if parsed.get("_has_notice_data"):
                    eis_notice_meta = parsed
                    metadata["notice_source_label"] = parsed.get("source_label", "электронное извещение ЕИС")
                    break

    card_meta = {
        "nmck": procurement.get("initial_price"),
        "publication_date": procurement.get("publication_date"),
        "submission_deadline": procurement.get("deadline"),
        "delivery_term": procurement.get("delivery_term"),
        "customer_name": procurement.get("customer_name"),
        "procedure_type": procurement.get("procedure_type"),
    }

    from src.modules.tender_operator_agent_demo.customer_role_facts import (
        resolve_customer_name,
    )

    doc_meta: dict[str, Any] = {}
    # Role-specific texts keep their authority; the combined text is only a
    # lowest-priority fallback for explicit customer-role patterns.
    customer_resolution = resolve_customer_name(
        notice_text=notice_text,
        contract_draft_text=contract_draft_text,
        technical_spec_text=technical_spec_text,
        combined_text=combined_text,
    )
    customer_candidate = customer_resolution.value if customer_resolution is not None else None
    if customer_candidate:
        doc_meta["customer_name"] = customer_candidate
        if metadata.get("mode") == "procurement_search_intake" or missing_value(metadata.get("customer_name")):
            metadata["customer_name"] = customer_candidate
        if metadata.get("mode") == "procurement_search_intake" or missing_value(procurement.get("customer_name")):
            procurement["customer_name"] = customer_candidate

    if missing_value(metadata.get("updated_date")) and missing_value(procurement.get("updated_date")):
        updated_date = updated_date_from_text(notice_text)
        if updated_date:
            metadata["updated_date"] = updated_date
            procurement["updated_date"] = updated_date

    structured = merge_structured_metadata(eis_notice_meta, card_meta, doc_meta)
    apply_structured_metadata_to_procurement(procurement, structured)
    metadata["_structured_metadata"] = structured

    if structured.get("procurement_subject"):
        subject_entry = structured["procurement_subject"]
        procurement["procurement_subject"] = subject_entry["value"]
        procurement["title_source_reference"] = subject_entry.get("source_reference")
        metadata["procurement_title"] = subject_entry["value"]
        metadata["tender_title"] = subject_entry["value"]
    for key in ("customer_name", "customer_inn", "customer_kpp"):
        entry = structured.get(key)
        if entry:
            procurement[key] = entry["value"]
            metadata[key] = entry["value"]
    delivery_entry = structured.get("delivery_place")
    if delivery_entry:
        delivery_value = delivery_entry["value"]
        procurement["delivery_place"] = delivery_value
        metadata["delivery_place"] = delivery_value
        metadata["delivery_address"] = delivery_value
        metadata["delivery_region"] = delivery_value.split(",", 1)[0]
        metadata["delivery_status"] = "known"
    okpd2_entry = structured.get("okpd2_codes")
    if okpd2_entry:
        metadata["okpd2_codes"] = okpd2_entry["value"]
        procurement["okpd2_codes"] = okpd2_entry["value"]
    for key, metadata_key in (("publication_date", "publication_date"), ("deadline", "deadline")):
        entry = structured.get(key)
        if entry:
            metadata[metadata_key] = entry["value"]
    metadata["_field_evidence"] = {
        field: entry.get("source_reference")
        for field, entry in (
            ("procurement_title", structured.get("procurement_subject")),
            ("publication_datetime", structured.get("publication_date")),
            ("application_deadline", structured.get("deadline")),
            ("nmck", structured.get("initial_price")),
            ("customer_name", structured.get("customer_name")),
            ("delivery_place", structured.get("delivery_place")),
            ("okpd2_codes", structured.get("okpd2_codes")),
        )
        if entry
    }

    if eis_notice_meta.get("_has_notice_data"):
        metadata["notice_source_label"] = eis_notice_meta.get("source_label", "электронное извещение ЕИС")
        procurement["structured_source_label"] = metadata["notice_source_label"]
    elif not procurement.get("structured_source_label"):
        procurement["structured_source_label"] = "карточка ЕИС"
        metadata["notice_source_label"] = "карточка ЕИС"

    if procurement:
        metadata["procurement"] = procurement
    return metadata
