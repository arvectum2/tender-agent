"""Product-owned deterministic goods projection; injected legacy helpers preserve call semantics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def project_build_goods_preliminary_analysis(
    *,
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    technical_spec_text: str,
    contract_draft_text: str,
    notice_text: str,
    _cleanup_delivery_address,
    _cleanup_tabular_value,
    _collect_goods_supply_items_from_documents,
    _dedupe_text_items,
    _extract_goods_spec_table,
    _extract_inline_goods_field,
    _extract_notice_delivery_deadline,
    _extract_notice_price,
    _match_first,
    _match_first_dotall,
    _normalize_analysis_sentence,
    _parse_float,
    _shorten_acceptance_terms,
    _shorten_payment_terms,
    _supply_item_to_row,
) -> dict[str, Any]:
    tz_text = technical_spec_text or ""
    contract_text = contract_draft_text or ""
    notice = notice_text or ""
    initial_price = _extract_notice_price(metadata, notice, contract_text)
    supply_items = _collect_goods_supply_items_from_documents(documents)
    spec_rows = [
        _supply_item_to_row(item) for item in supply_items
    ] or _extract_goods_spec_table(tz_text)
    delivery_deadline = _extract_inline_goods_field(
        tz_text,
        ("Срок поставки", "Сроки поставки товара"),
        stop_markers=(
            "Требования к качеству",
            "Требования к безопасности",
            "Условия оплаты",
            "Адрес поставки",
            "Место поставки",
            "Условия поставки",
            "Порядок поставки",
        ),
    ) or _extract_notice_delivery_deadline(notice)
    delivery_deadline = _cleanup_tabular_value(delivery_deadline) or delivery_deadline
    delivery_address = _extract_inline_goods_field(
        tz_text,
        ("Место поставки", "Место поставки товаров", "Адрес поставки товара"),
        stop_markers=(
            "Расходы по доставке",
            "Условия поставки",
            "Срок поставки",
            "Сроки поставки товара",
            "Порядок поставки",
            "Условия оплаты",
        ),
    )
    delivery_address = _cleanup_delivery_address(delivery_address) or delivery_address
    payment_terms = _match_first(
        contract_text,
        (
            "в течение\\s+(\\d+\\s*\\([^)]+\\)\\s*рабочих дней[^.]+документа о приемке)",
            "в течение\\s+(\\d+\\s*рабочих дней[^.]+документа о приемке)",
            "Оплата[^.]*?в течение\\s+([^.]+)",
        ),
    )
    acceptance_window = _match_first(
        contract_text,
        (
            "Не позднее\\s+(\\d+\\s*\\([^)]+\\)\\s*рабочих дней[^.]+документа о приемке)",
            "Не позднее\\s+(\\d+\\s*рабочих дней[^.]+документа о приемке)",
        ),
    )
    execution_security = _match_first(
        contract_text + "\n" + notice,
        ("обеспечени[ея]\\s+исполнения\\s+контракта[^.]{0,120}",),
    )
    execution_security_percent = _match_first_dotall(
        notice + "\n" + contract_text,
        (
            "contractGuarantee[\\s\\S]{0,600}?<(?:\\w+:)?part>(\\d+(?:[.,]\\d+)?)</(?:\\w+:)?part>",
            "обеспечени[ея]\\s+исполнения\\s+контракта[^%\\n]{0,200}?(\\d+(?:[.,]\\d+)?)\\s*%",
        ),
    )
    contract_terms = []
    if payment_terms:
        contract_terms.append(f"Условия оплаты: в течение {payment_terms}.")
    if execution_security:
        security_text = "Обеспечение исполнения контракта: да"
        if execution_security_percent:
            security_text += (
                f", {execution_security_percent.replace('.', ',')}% от НМЦК"
            )
        contract_terms.append(security_text + ".")
    if acceptance_window:
        short_acceptance = _shorten_acceptance_terms(acceptance_window)
        if short_acceptance:
            contract_terms.append(f"Срок приемки: {short_acceptance.rstrip('.')}.")
    if "цена контракта является твердой" in contract_text.lower():
        contract_terms.append(
            "Цена контракта: твердая, без индексации на период исполнения."
        )
    contract_terms = _dedupe_text_items(
        [_normalize_analysis_sentence(item) or item for item in contract_terms[:6]]
    )
    total_meter_quantity = sum(
        _parse_float(item.quantity) or 0
        for item in supply_items
        if (item.unit or "") == "м"
    )
    total_positions = len(supply_items)
    top_position = max(
        supply_items, key=lambda item: _parse_float(item.quantity) or 0, default=None
    )
    overview = [
        f"Предмет закупки: {metadata.get('tender_title') or 'поставка товаров'}"
    ]
    if initial_price:
        overview.append(f"НМЦК: {initial_price} руб.")
    if spec_rows:
        overview.append("В ТЗ выделена табличная спецификация по товарам.")
    if total_positions:
        overview.append(f"Количество позиций: {total_positions}.")
    if total_meter_quantity:
        quantity_text = (
            int(total_meter_quantity)
            if float(total_meter_quantity).is_integer()
            else total_meter_quantity
        )
        overview.append(f"Общий объём кабеля/провода: {quantity_text} м.")
    if delivery_address:
        overview.append(
            f"Адрес поставки: {(_normalize_analysis_sentence(delivery_address) or delivery_address).rstrip('.')}."
        )
    if delivery_deadline:
        overview.append(
            f"Срок поставки: {(_normalize_analysis_sentence(delivery_deadline) or delivery_deadline).rstrip('.')}."
        )
    if payment_terms:
        short_payment_terms = _shorten_payment_terms(payment_terms)
        if short_payment_terms:
            overview.append(f"Оплата: {short_payment_terms.rstrip('.')}")
    overview = _dedupe_text_items(
        [_normalize_analysis_sentence(item) or item for item in overview[:7]]
    )
    compliance_highlights = _dedupe_text_items(
        [
            "Нужно подтвердить соответствие каждой позиции ГОСТ, ТУ и характеристикам ТЗ.",
            "Для позиций с обязательной сертификацией нужно получить сертификаты, декларации и паспорта качества.",
            "Аналоги допустимы только при полном соответствии характеристикам и требованиям заказчика.",
            "До участия нужно проверить включение доставки и разгрузки в цену поставщика.",
        ]
    )
    delivery_model = _dedupe_text_items(
        [
            _normalize_analysis_sentence(
                f"Поставка выполняется по адресу заказчика: {delivery_address}"
            )
            if delivery_address
            else None,
            _normalize_analysis_sentence(f"Срок поставки: {delivery_deadline}")
            if delivery_deadline
            else None,
            "Поставка выполняется по заявке заказчика; важно подтвердить складской остаток и срок отгрузки.",
            "Доставка и разгрузка должны быть подтверждены поставщиком отдельно.",
        ]
    )
    next_actions = _dedupe_text_items(
        [
            "Сверить извлечённые позиции с ТЗ и НМЦК.xlsx по количеству, единицам и ГОСТ.",
            "Запросить КП по каждой позиции с ценой за единицу, суммой, НДС и сроком поставки.",
            "Подтвердить наличие товара, документы качества и логистику до адреса заказчика.",
        ]
    )
    return {
        "overview": overview,
        "compliance_highlights": compliance_highlights,
        "delivery_model": delivery_model,
        "contract_highlights": contract_terms,
        "next_actions": next_actions,
        "supply_items": [item.__dict__ for item in supply_items],
        "extracted_fields": _dedupe_text_items(
            [
                "НМЦК" if initial_price else "",
                "позиции поставки" if spec_rows else "",
                "срок поставки" if delivery_deadline else "",
                "адрес поставки" if delivery_address else "",
            ]
        ),
        "procurement_kind": "goods",
        "supply_section_note": "Позиции поставки собраны из ТЗ, спецификаций и НМЦК.xlsx."
        if spec_rows
        else "Позиции поставки не извлечены автоматически. Нужна ручная сверка ТЗ и приложений.",
        "spec_table": {
            "columns": [
                "№",
                "Наименование",
                "Кол-во",
                "Ед. изм.",
                "Ключевые характеристики",
                "ГОСТ / норматив",
                "Эквивалент",
                "Цена за ед., руб.",
                "Сумма, руб.",
                "Источник",
            ],
            "rows": spec_rows,
        },
        "largest_position": top_position.name if top_position else None,
    }
