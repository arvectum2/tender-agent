"""Product-owned software/integration preliminary procurement report projection.

This is a classification-dependent fallback, not authenticated EIS evidence.
The legacy upload module injects its source-aware helpers; no I/O here.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_software_preliminary_analysis(
    metadata: dict[str, Any],
    documents: list[Any],
    combined: str,
    tz_text: str,
    contract_text: str,
    notice: str,
    scope: dict[str, Any],
    procurement_kind: str,
    *,
    _build_software_work_rows: Callable[..., list[dict[str, str]]],
    _extract_notice_price: Callable[..., str | None],
    _extract_notice_service_deadline: Callable[..., str | None],
    _extract_notice_delivery_deadline: Callable[..., str | None],
    _cleanup_tabular_value: Callable[..., str | None],
    _match_first: Callable[..., str | None],
    _dedupe_text_items: Callable[..., list[str]],
) -> dict[str, Any]:
    work_rows = _build_software_work_rows(documents)
    initial_price = _extract_notice_price(metadata, notice, contract_text)
    deadline = metadata.get("deadline") or _extract_notice_service_deadline(notice) or _extract_notice_delivery_deadline(notice)
    delivery_term = metadata.get("procurement", {}).get("delivery_term") if isinstance(metadata.get("procurement"), dict) else None
    tender_title = metadata.get("tender_title") or _cleanup_tabular_value(
        _match_first(combined, (r"Наименование работ:\s*(.+?)(?:\n|$)",))
    ) or "не указан"
    overview = [
        f"Предмет закупки: {tender_title}",
        f"НМЦК: {initial_price} руб." if initial_price else "",
        f"Тип закупки: {procurement_kind}.",
        f"Срок исполнения / подачи: {deadline}." if deadline else "",
        "Результат для заказчика: модифицированный модуль, интеграции и лицензионный пакет." if work_rows else "",
    ]
    compliance = [
        "Нужно проверить полноту функциональных требований по каждому блоку доработки.",
        "Требования к интеграциям, доступам и форматам обмена должны быть подтверждены документами и перепиской с заказчиком.",
        "Нужно отдельно проверить требования к передаче лицензии, прав и итоговой документации.",
    ]
    contract_terms = []
    if delivery_term:
        contract_terms.append(f"Срок исполнения по документам: {delivery_term}.")
    if "акт" in contract_text.lower() or "приемк" in contract_text.lower():
        contract_terms.append("В проекте контракта есть условия приемки и закрывающих документов.")
    if "лиценз" in (tz_text + "\n" + contract_text).lower():
        contract_terms.append("В составе результата работ фигурирует передача лицензии или прав использования.")
    return {
        "overview": [item for item in overview if item][:6],
        "compliance_highlights": compliance[:6],
        "delivery_model": [
            "Работы зависят от внешних систем, доступов и интеграционного контура заказчика.",
            "Часть требований относится к программной доработке, а не к поставке товара.",
        ],
        "contract_highlights": contract_terms[:6],
        "next_actions": [
            "Разбить объем работ по функциональным блокам и запросить оценку трудозатрат по каждому блоку.",
            "Уточнить порядок предоставления доступов к СМЭВ, ЕРН и витрине Минобороны.",
            "Проверить критерии приемки, тестирования и пакет лицензионных документов.",
        ],
        "extracted_fields": _dedupe_text_items(
            [
                "НМЦК" if initial_price else "",
                "функциональные блоки" if work_rows else "",
                "интеграции" if any("Интеграция" in row.get("Блок работ / результат", "") for row in work_rows) else "",
                "лицензия" if "лиценз" in (tz_text + contract_text).lower() else "",
            ]
        ),
        "procurement_kind": procurement_kind,
        "scope": scope,
        "supply_section_note": (
            "Состав работ собран по техническим документам и проекту контракта."
            if work_rows
            else "Полный смысловой разбор состава работ не выполнен автоматически. Нужна ручная проверка ТЗ."
        ),
        "spec_table": {
            "columns": ["№", "Блок работ / результат", "Что нужно сделать", "Входные/внешние системы", "Результат для заказчика", "Критерии приёмки", "Источник"],
            "rows": work_rows,
        },
    }
