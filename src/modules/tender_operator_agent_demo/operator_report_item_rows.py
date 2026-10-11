"""Procurement-owned source-preserving report item row projection.

This module does not ingest source documents or mutate data. Dependencies are
injected by the legacy facade for runtime compatibility and testability.
"""
from __future__ import annotations

from typing import Any


def build_item_rows(
    preliminary: dict[str, Any],
    *,
    get_settings: Any,
    _format_source_location: Any,
    _quality_gate_status: Any,
    UNKNOWN: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    graph_model = preliminary.get("canonical_procurement_model") or {}
    mode = get_settings().source_graph_mode
    if mode not in {"legacy", "shadow", "production"}:
        raise ValueError("AI_CORP_SOURCE_GRAPH_MODE must be legacy, shadow, or production")
    if mode == "production" and not graph_model:
        raise RuntimeError("SOURCE_GRAPH_MODEL_REQUIRED")
    if graph_model:
        source_items = graph_model.get("canonical_items", [])
        if mode == "production" and source_items is None:
            raise RuntimeError("SOURCE_GRAPH_MODEL_REQUIRED")
    else:
        source_items = None
    service_items = preliminary.get("service_items") or []
    supply_items = preliminary.get("supply_items") or []
    spec_rows = preliminary.get("spec_table", {}).get("rows", [])
    if source_items is None:
        if mode == "production":
            raise RuntimeError("LEGACY_ITEM_PATH_USED_IN_PRODUCTION")
        source_items = (
            max((service_items, supply_items, spec_rows), key=len)
            if preliminary.get("procurement_kind") == "services"
            else supply_items or service_items or spec_rows
        )
    for sequence, item in enumerate(source_items, start=1):
        official_name = item.get("official_name") or item.get("original_name") or item.get("name") or item.get("Наименование") or UNKNOWN
        if official_name == UNKNOWN:
            continue
        name = item.get("display_name") or official_name
        quantity = item.get("quantity")
        if quantity is None:
            quantity = item.get("Кол-во") if item.get("Кол-во") not in (None, "не указано") else None
        unit = item.get("unit") or item.get("unit_original") or item.get("Ед. изм.")
        evidence_ids = item.get("evidence_ids", [])
        if not evidence_ids and item.get("evidence_id"):
            evidence_ids = [item["evidence_id"]]
        rows.append({
            "stable_item_id": item.get("canonical_item_id") or item.get("stable_item_id") or item.get("evidence_id") or f"line-{sequence}",
            "sequence": sequence,
            "official_name": official_name,
            "display_name": name,
            "original_name": name,
            "normalized_name": item.get("normalized_name") or item.get("name") or name,
            "unit_original": unit or UNKNOWN,
            "unit_normalized": unit,
            "quantity": quantity,
            "quantity_status": item.get("quantity_status") or ("specified" if quantity is not None and unit else "not_specified"),
            "quantity_display": "Не указан документацией" if quantity is None else str(quantity),
            "unit_price": item.get("unit_price"),
            "currency": item.get("currency") or "RUB",
            "pricing_basis": item.get("pricing_basis") or "unknown",
            "line_total": item.get("total_price"),
            "line_total_display": "Не рассчитывается",
            "evidence_ids": evidence_ids,
            "source_document_id": item.get("source_document") or (item.get("Источник") or None),
            "source_row": _format_source_location(item.get("source_row_number") or item.get("source_row")),
            "warnings": item.get("warnings", []),
            "field_issues": item.get("field_issues", []),
            "name_source_type": item.get("name_source_type", "unresolved"),
            "name_source_path": item.get("name_source_path"),
            "quantity_source_path": item.get("quantity_source_path"),
            "unit_source_path": item.get("unit_source_path"),
            "source_record_id": item.get("source_record_id"),
            "extraction_strategy": item.get("extraction_strategy"),
            "field_provenance": item.get("field_provenance", {}),
            "characteristics": item.get("characteristics", []),
            "quality_gate_status": _quality_gate_status(item, str(official_name), quantity, unit),
        })
    return rows
