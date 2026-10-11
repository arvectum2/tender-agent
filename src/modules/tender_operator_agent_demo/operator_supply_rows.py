"""Pure procurement product projections; source-oriented only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import SupplyItem


def supply_item_to_row(item: SupplyItem) -> dict[str, Any]:
    characteristics = (
        "; ".join(item.characteristics)
        if item.characteristics
        else "Требуется сверка характеристик по ТЗ."
    )
    return {
        "№": item.item_no or "—",
        "Наименование": item.display_name or item.name,
        "official_name": item.official_name or item.name,
        "display_name": item.display_name or item.name,
        "Кол-во": item.quantity or "не указано",
        "Ед. изм.": item.unit or "—",
        "Ключевые характеристики": characteristics,
        "ГОСТ / норматив": ", ".join(item.gost) if item.gost else "—",
        "Эквивалент": "да" if item.equivalent_allowed else "нет",
        "Цена за ед., руб.": item.unit_price or "—",
        "Сумма, руб.": item.total_price or "—",
        "Источник": ", ".join(item.source_documents or [item.source_document]),
        "quantity_status": item.quantity_status,
        "evidence_ids": item.evidence_ids
        or ([item.evidence_id] if item.evidence_id else []),
        "key_characteristics": item.characteristics[:5],
        "name_source_type": item.name_source_type,
        "name_source_path": item.name_source_path,
        "quantity_source_path": item.quantity_source_path,
        "unit_source_path": item.unit_source_path,
        "source_row_number": item.source_row_number,
        "source_record_id": item.source_record_id,
        "extraction_strategy": item.extraction_strategy,
        "okpd2": item.okpd2,
        "ktru": item.ktru,
    }


def service_item_analysis_rows(items: list[SupplyItem]) -> list[dict[str, Any]]:
    """Serialize extracted rows without converting an unspecified volume to zero."""
    return [
        {
            "stable_item_id": item.evidence_id or f"service-{index}",
            "original_name": item.name,
            "normalized_name": item.name,
            "unit": item.unit_original or item.unit,
            "unit_price": item.unit_price,
            "pricing_basis": item.pricing_basis,
            "quantity": item.quantity,
            "quantity_status": item.quantity_status,
            "technical_requirements": item.characteristics,
            "evidence_ids": [item.evidence_id] if item.evidence_id else [],
            "source_document": item.source_document,
            "source_row_number": item.source_row_number,
        }
        for index, item in enumerate(items, start=1)
    ]
