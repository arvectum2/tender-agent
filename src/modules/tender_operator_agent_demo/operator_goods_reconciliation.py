"""Product-owned deterministic goods projection; injected legacy helpers preserve call semantics."""

# ruff: noqa: F841, C401 -- retain source AST exactly; legacy cleanup is a separate change.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
        SupplyItem,
    )


def project_merge_supply_items(
    items: list[SupplyItem],
    *,
    _is_line_item_name,
    _normalize_supply_name_key,
    _normalize_supply_unit,
    _summarize_supply_characteristics,
) -> list[SupplyItem]:
    """Create canonical procurement items while retaining every source as evidence.

    A quantity can be absent in a DOCX representation of a purchase object and
    present in XML/XLSX.  It must complement the same item rather than create a
    second row merely because the less complete representation lacks a value.
    """
    merged: list[SupplyItem] = []
    for item in items:
        if item.record_type != "line_item" or not _is_line_item_name(item.name):
            continue
        if item.item_type == "service":
            item.evidence_ids = list(
                dict.fromkeys(
                    item.evidence_ids
                    or ([item.evidence_id] if item.evidence_id else [])
                )
            )
            item.official_name = item.official_name or item.name
            item.display_name = item.display_name or item.name
            merged.append(item)
            continue
        name_key = _normalize_supply_name_key(item.name)
        if not name_key:
            continue
        item.evidence_ids = list(
            dict.fromkeys(
                item.evidence_ids or ([item.evidence_id] if item.evidence_id else [])
            )
        )
        item.official_name = item.official_name or item.name
        item.display_name = item.display_name or item.name
        item_unit = _normalize_supply_unit(item.unit)
        signature = tuple(
            sorted(
                _normalize_supply_name_key(value)
                for value in item.characteristics
                if value
            )
        )
        existing = next(
            (
                candidate
                for candidate in merged
                if (
                    _normalize_supply_name_key(candidate.name) == name_key
                    or bool(
                        set(
                            (
                                token
                                for token in _normalize_supply_name_key(
                                    candidate.name
                                ).split()
                                if len(token) >= 5
                            )
                        )
                        & set((token for token in name_key.split() if len(token) >= 5))
                    )
                )
                and (
                    not _normalize_supply_unit(candidate.unit)
                    or not item_unit
                    or _normalize_supply_unit(candidate.unit) == item_unit
                )
                and (
                    not candidate.quantity
                    or not item.quantity
                    or candidate.quantity == item.quantity
                )
                and (
                    not candidate.okpd2
                    or not item.okpd2
                    or candidate.okpd2 == item.okpd2
                )
                and (not candidate.ktru or not item.ktru or candidate.ktru == item.ktru)
            ),
            None,
        )
        if existing is None:
            merged.append(item)
            continue
        if not existing.quantity and item.quantity:
            existing.quantity = item.quantity
        if not existing.unit and item.unit:
            existing.unit = item.unit
        if not existing.unit_price and item.unit_price:
            existing.unit_price = item.unit_price
        if not existing.total_price and item.total_price:
            existing.total_price = item.total_price
        if item.gost:
            existing.gost = _summarize_supply_characteristics(
                existing.gost + item.gost, limit=4
            )
        if item.characteristics:
            existing.characteristics = _summarize_supply_characteristics(
                existing.characteristics + item.characteristics, limit=6
            )
        existing.equivalent_allowed = (
            existing.equivalent_allowed or item.equivalent_allowed
        )
        existing.confidence = (
            "high"
            if "high" in {existing.confidence, item.confidence}
            else existing.confidence
        )
        for source_document in item.source_documents or [item.source_document]:
            if source_document not in existing.source_documents:
                existing.source_documents.append(source_document)
        existing.evidence_ids = list(
            dict.fromkeys(existing.evidence_ids + item.evidence_ids)
        )
        if (
            item.name_source_type == "structured_direct_name"
            and existing.name_source_type != "structured_direct_name"
        ):
            existing.name = item.name
            existing.official_name = item.name
            existing.display_name = item.name
            existing.name_source_type = item.name_source_type
            existing.name_source_path = item.name_source_path
        if (
            existing.source_document != item.source_document
            and item.source_kind == "technical_spec"
        ):
            existing.source_document = item.source_document
            existing.source_kind = item.source_kind
            existing.raw_fragment = item.raw_fragment or existing.raw_fragment

    def sort_key(item: SupplyItem) -> tuple[int, str]:
        try:
            number = int(item.item_no or "999")
        except ValueError:
            number = 999
        return (number, item.name.lower())

    name_counts: dict[str, int] = {}
    for item in merged:
        name_counts[_normalize_supply_name_key(item.official_name or item.name)] = (
            name_counts.get(
                _normalize_supply_name_key(item.official_name or item.name), 0
            )
            + 1
        )
    for item in merged:
        official_name = item.official_name or item.name
        characteristics = _summarize_supply_characteristics(
            item.characteristics, limit=3
        )
        if (
            name_counts[_normalize_supply_name_key(official_name)] > 1
            and characteristics
        ):
            item.display_name = f"{official_name} — {', '.join(characteristics)}"
        else:
            item.display_name = official_name
    return sorted(merged, key=sort_key)


def project_collect_unmerged_source_items(
    documents: list[AnalyzedDocument],
    *,
    SupplyItem,
    _extract_service_items_from_nmck_text,
    _extract_supply_items_from_notification_xml,
    _extract_supply_items_from_spec_text,
    _extract_supply_items_from_xlsx_text,
    _is_line_item_name,
    _normalize_supply_name,
    _normalize_supply_name_key,
    extract_goods_source_facts,
) -> list[SupplyItem]:
    """Return per-document extractor rows before legacy reconciliation.

    The production source graph consumes these rows.  `_collect_supply_items`
    remains a compatibility presentation helper and is never its value source.
    """
    extracted: list[SupplyItem] = []
    for doc in documents:
        text = doc.text or ""
        if not text:
            continue
        lowered_name = doc.display_name.lower()
        if doc.role == "technical_spec" or any(
            token in lowered_name
            for token in (
                "техническ",
                "описание объекта",
                "спецификац",
                "перечень",
                "ведомост",
            )
        ):
            extracted.extend(
                _extract_supply_items_from_spec_text(text, doc.display_name)
            )
        if (
            doc.extension in {".xlsx", ".xls"}
            or "нмцк" in lowered_name
            or "обоснование" in lowered_name
        ):
            extracted.extend(
                _extract_supply_items_from_xlsx_text(text, doc.display_name)
            )
            extracted.extend(
                _extract_service_items_from_nmck_text(text, doc.display_name)
            )
        if (
            doc.extension == ".xml"
            or "purchasenotice" in text.lower()
            or "epnotification" in text.lower()
            or ("purchaseobject" in text.lower())
        ):
            extracted.extend(
                _extract_supply_items_from_notification_xml(text, doc.display_name)
            )
    existing_names = {_normalize_supply_name_key(item.name) for item in extracted}
    for fact in extract_goods_source_facts(documents):
        if fact.fact_type != "PRODUCT_ITEM":
            continue
        name = _normalize_supply_name(fact.value)
        key = _normalize_supply_name_key(name)
        if not _is_line_item_name(name) or key in existing_names:
            continue
        extracted.append(
            SupplyItem(
                item_no=None,
                name=name,
                quantity=None,
                unit=None,
                characteristics=[],
                gost=[],
                equivalent_allowed=None,
                source_document=fact.source_document,
                source_kind="source_fact",
                confidence=fact.confidence,
                raw_fragment=fact.excerpt,
                source_documents=[fact.source_document],
                quantity_status="not_specified",
                source_row_number=fact.source_row_number,
                evidence_id=fact.fact_id,
                extraction_strategy=fact.extraction_strategy,
            )
        )
        existing_names.add(key)
    return extracted
