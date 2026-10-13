"""Domain-owned deterministic renderer or service analysis; upload-I/O independent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def project_build_services_preliminary_analysis(
    *,
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    notice_text: str,
    contract_draft_text: str,
    _collect_supply_items,
    _service_subject_from_sources,
    _service_okpd2_from_sources,
    _is_vehicle_maintenance_services,
    _extract_notice_price,
    _service_item_analysis_rows,
) -> dict[str, Any]:
    """Deterministic, domain-safe analysis for a unit-priced service catalogue."""
    service_items = [
        item for item in _collect_supply_items(documents) if item.item_type == "service"
    ]
    subject = _service_subject_from_sources(metadata, notice_text, documents)
    okpd2 = _service_okpd2_from_sources(notice_text, documents)
    profile = (
        "vehicle_maintenance_services"
        if _is_vehicle_maintenance_services(subject, okpd2, service_items)
        else "general_services"
    )
    initial_price = _extract_notice_price(metadata, notice_text, contract_draft_text)
    contract_missing = not bool(contract_draft_text.strip())
    rows = [
        {
            "№": str(index),
            "Наименование услуги": item.name,
            "Объём/количество": "не определён документацией"
            if item.quantity is None
            else item.quantity,
            "Единица": item.unit_original
            or item.unit
            or "не извлечено — требуется проверка",
            "Цена единицы, руб.": item.unit_price
            or "не извлечено — требуется проверка",
            "Источник": item.source_document,
            "Evidence": item.evidence_id or "не извлечено — требуется проверка",
        }
        for (index, item) in enumerate(service_items, start=1)
    ]
    coverage = {
        "extracted_item_count": len(service_items),
        "analyzed_item_count": len(service_items),
        "ignored_item_count": 0,
        "item_evidence_coverage": 1.0
        if service_items and all(item.evidence_id for item in service_items)
        else 0.0,
        "grouping_coverage": 1.0 if service_items else 0.0,
    }
    return {
        "overview": [
            f"Предмет закупки: {subject}",
            f"ОКПД2: {okpd2}." if okpd2 else "ОКПД2 не извлечён — требуется проверка.",
            f"НМЦК: {initial_price} руб."
            if initial_price
            else "НМЦК не извлечена — требуется проверка.",
            f"Извлечено и проанализировано позиций услуг: {len(service_items)}.",
            "В документации указаны единичные расценки; фиксированный объём отдельных услуг не определён.",
        ],
        "compliance_highlights": [
            "Необходимо подтвердить наличие специалистов, оборудования и ремонтной базы для перечня услуг до решения об участии."
        ],
        "delivery_model": [
            "Объём услуг определяется потребностью заказчика; единичные расценки не образуют подтверждённую сумму по каждой операции."
        ],
        "contract_highlights": [
            "Проект контракта отсутствует в доступном наборе документов; оплата, приемка, ответственность и обеспечение не оценены."
        ]
        if contract_missing
        else ["Проект контракта доступен и требует отдельной документальной проверки."],
        "next_actions": [
            "Получить проект контракта и проверить оплату, приемку, ответственность, обеспечение и сроки.",
            "Сопоставить единичные расценки с внутренней стоимостью нормо-часа и иными подтверждёнными затратами.",
            "Подтвердить возможность выполнения полного перечня услуг: специалистов, оборудование и ремонтную базу.",
            "Уточнить порядок учета запасных частей и материалов, если он не раскрыт первичными документами.",
        ],
        "extracted_fields": [
            "предмет закупки",
            "ОКПД2" if okpd2 else "",
            "НМЦК" if initial_price else "",
            "единичные расценки",
            "объём услуг не определён",
        ],
        "procurement_kind": "services",
        "domain_profile": profile,
        "service_items": _service_item_analysis_rows(service_items),
        "item_coverage": coverage,
        "source_completeness": "partial" if contract_missing else "partial",  # noqa: RUF034
        "missing_documents": ["draft_contract"] if contract_missing else [],
        "supply_section_note": "Перечень услуг и единичные расценки собраны из таблицы обоснования НМЦК; фиксированный объём по строкам не заявлен.",
        "spec_table": {
            "columns": [
                "№",
                "Наименование услуги",
                "Объём/количество",
                "Единица",
                "Цена единицы, руб.",
                "Источник",
                "Evidence",
            ],
            "rows": rows,
        },
    }
