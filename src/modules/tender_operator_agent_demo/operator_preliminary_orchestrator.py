"""Procurement preliminary analysis orchestration, injected from the legacy compatibility facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def project_build_preliminary_procurement_analysis(
    *,
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    technical_spec_text: str,
    contract_draft_text: str,
    notice_text: str,
    _build_goods_preliminary_analysis,
    _build_services_preliminary_analysis,
    _build_software_work_rows,
    _build_supply_rows,
    _classify_procurement_scope,
    _cleanup_tabular_value,
    _collect_matches,
    _collect_supply_items,
    _dedupe_text_items,
    _extract_notice_delivery_deadline,
    _extract_notice_price,
    _extract_notice_service_deadline,
    _format_money_value,
    _match_first,
    _match_first_dotall,
    _normalize_analysis_sentence,
    _rewrite_compliance_highlight,
    _rewrite_delivery_model_item,
    _shorten_acceptance_terms,
    _shorten_payment_terms,
    build_software_preliminary_analysis,
    build_training_location_action,
    extract_training_candidate_facts,
    re,
) -> dict[str, Any]:
    tz_text = technical_spec_text or ""
    contract_text = contract_draft_text or ""
    notice = notice_text or ""
    combined = "\n".join(part for part in (tz_text, contract_text, notice) if part)
    scope = _classify_procurement_scope(metadata, documents, notice)
    procurement_kind = scope["procurement_primary_scope"]
    extracted_service_items = [
        item for item in _collect_supply_items(documents) if item.item_type == "service"
    ]
    if extracted_service_items and procurement_kind in {"unresolved", "generic"}:
        procurement_kind = "services"
    elif _collect_supply_items(documents) and procurement_kind in {
        "unresolved",
        "generic",
    }:
        procurement_kind = "goods"
    if scope["goods_extraction_applicable"] and procurement_kind in {"goods", "mixed"}:
        preliminary = _build_goods_preliminary_analysis(
            metadata=metadata,
            documents=documents,
            technical_spec_text=technical_spec_text,
            contract_draft_text=contract_draft_text,
            notice_text=notice_text,
        )
        preliminary["procurement_kind"] = procurement_kind
        preliminary["scope"] = scope
        return preliminary
    training_markers = ("обучени", "слушател", "учебн", "повышени[яе] квалификац")
    is_training_service = any(
        re.search(marker, combined, re.IGNORECASE) for marker in training_markers
    )
    if procurement_kind == "services" and (not is_training_service):
        return _build_services_preliminary_analysis(
            metadata=metadata,
            documents=documents,
            notice_text=notice,
            contract_draft_text=contract_text,
        )
    if procurement_kind in {"rental", "unresolved", "works"}:
        tender_title = metadata.get("tender_title") or "не указан"
        fallback_kind = "generic" if procurement_kind == "works" else procurement_kind
        return {
            "overview": [
                f"Предмет закупки: {tender_title}",
                f"Тип закупки: {procurement_kind}.",
            ],
            "compliance_highlights": [],
            "delivery_model": [],
            "contract_highlights": [],
            "next_actions": [
                "Подтвердить предмет закупки и применимый category-specific workflow по первичным документам."
            ],
            "extracted_fields": [],
            "procurement_kind": fallback_kind,
            "scope": scope,
            "supply_section_note": "Товарный анализ не запускается до подтверждения категории закупки.",
            "spec_table": {"columns": [], "rows": []},
        }
    if procurement_kind in {"mixed", "software_modification", "integration", "license"}:
        return build_software_preliminary_analysis(
            metadata,
            documents,
            combined,
            tz_text,
            contract_text,
            notice,
            scope,
            procurement_kind,
            _build_software_work_rows=_build_software_work_rows,
            _extract_notice_price=_extract_notice_price,
            _extract_notice_service_deadline=_extract_notice_service_deadline,
            _extract_notice_delivery_deadline=_extract_notice_delivery_deadline,
            _cleanup_tabular_value=_cleanup_tabular_value,
            _match_first=_match_first,
            _dedupe_text_items=_dedupe_text_items,
        )
    (
        service_subject,
        training_format,
        hours,
        listeners,
        service_deadline,
        location,
        initial_price,
        payment_terms,
        execution_security,
        execution_security_percent,
        execution_security_amount,
        acceptance_window,
        unilateral_termination,
    ) = extract_training_candidate_facts(
        metadata,
        tz_text,
        contract_text,
        notice,
        _match_first=_match_first,
        _extract_notice_service_deadline=_extract_notice_service_deadline,
        _cleanup_tabular_value=_cleanup_tabular_value,
        _extract_notice_price=_extract_notice_price,
        _match_first_dotall=_match_first_dotall,
    )
    compliance_highlights = _collect_matches(
        tz_text,
        (
            "(согласован[^\\n.]*Федеральной службой по техническому и экспортному контролю[^\\n.]*)",
            "(выдать удостоверени[^\\n.]*повышении квалификации[^\\n.]*)",
            "(итогов[^\\n.]*аттестаци[^\\n.]*)",
            "(учебный план должен содержать[^\\n.]*)",
            "(раздаточн[^\\n.]*материал[^\\n.]*)",
            "(ГОСТ\\s*\\d+(?:-\\d+)?[^\\n.]*)",
        ),
        limit=6,
    )
    delivery_model = _collect_matches(
        tz_text,
        (
            "(Очно-заочная[^\\n.]*)",
            "(с применением дистанционных образовательных технологий[^\\n.]*)",
            "(60\\s*%\\s*времени[^\\n.]*)",
            "(40\\s*%\\s*времени[^\\n.]*)",
            "(с 09\\.00 до 18\\.00[^\\n.]*)",
            "(в городе [А-ЯЁA-Z][^;.\\n]*)",
        ),
        limit=6,
    )
    extracted_fields = [
        label
        for (label, value) in (
            ("НМЦК", initial_price),
            ("предмет закупки", service_subject),
            ("формат оказания услуг", training_format),
            ("объём программы", hours),
            ("количество слушателей", listeners),
            ("срок оказания услуг", service_deadline),
            ("место оказания услуг", location),
            ("условия оплаты", payment_terms),
            ("приёмка", acceptance_window),
        )
        if value
    ]
    overview: list[str] = []
    if service_subject:
        overview.append(f"Предмет закупки: {service_subject}")
    if initial_price:
        overview.append(f"НМЦК: {initial_price} руб.")
    if training_format:
        overview.append(f"Формат: {training_format}")
    if hours or listeners:
        overview.append(
            "Объём: "
            + ", ".join(
                part
                for part in (
                    hours,
                    f"{listeners} слушателей"
                    if listeners and listeners.isdigit()
                    else listeners,
                )
                if part
            )
        )
    if service_deadline:
        overview.append(f"Срок оказания услуг: {service_deadline}")
    if location:
        overview.append(f"Место оказания услуг: {location}")
    if payment_terms:
        short_payment_terms = _shorten_payment_terms(payment_terms)
        if short_payment_terms:
            overview.append(f"Оплата: {short_payment_terms.rstrip('.')}")
    overview = _dedupe_text_items(
        [_normalize_analysis_sentence(item) or item for item in overview[:6]]
    )
    compliance_highlights = [
        rewritten
        for rewritten in (
            _rewrite_compliance_highlight(item) for item in compliance_highlights[:6]
        )
        if rewritten
    ]
    compliance_highlights = _dedupe_text_items(compliance_highlights)
    delivery_model = [
        rewritten
        for rewritten in (
            _rewrite_delivery_model_item(item, procurement_kind)
            for item in delivery_model[:6]
        )
        if rewritten
    ]
    delivery_model = _dedupe_text_items(delivery_model)
    next_actions = [
        build_training_location_action(location, training_format),
        "Подтвердить наличие согласованной с ФСТЭК программы и право выдачи удостоверения о повышении квалификации."
        if any(
            "Федеральной службой по техническому и экспортному контролю" in item
            for item in compliance_highlights
        )
        else "Проверить обязательные допуски, программу и итоговые документы по обучению.",
        "До запроса ТКП уточнить ресурсы: график, преподаватели, аудитории, оборудование и учебные материалы.",
    ]
    next_actions = _dedupe_text_items(
        [_normalize_analysis_sentence(item) or item for item in next_actions[:4]]
    )
    contract_terms: list[str] = []
    if payment_terms:
        contract_terms.append(f"Условия оплаты: в течение {payment_terms}.")
    if execution_security:
        security_parts: list[str] = ["Обеспечение исполнения контракта: да"]
        if execution_security_percent:
            security_parts.append(
                f"{execution_security_percent.replace('.', ',')}% от НМЦК"
            )
        if execution_security_amount:
            amount_text = _format_money_value(execution_security_amount)
            if amount_text:
                security_parts.append(f"{amount_text} руб.")
        contract_terms.append(", ".join(security_parts) + ".")
    if acceptance_window:
        short_acceptance = _shorten_acceptance_terms(acceptance_window)
        if short_acceptance:
            contract_terms.append(f"Срок приемки: {short_acceptance.rstrip('.')}.")
    if "цена контракта является твердой" in contract_text.lower():
        contract_terms.append(
            "Цена контракта: твердая, без индексации на период исполнения."
        )
    if unilateral_termination:
        contract_terms.append(
            "Односторонний отказ от исполнения контракта предусмотрен по основаниям, указанным в договоре."
        )
    contract_terms = _dedupe_text_items(
        [_normalize_analysis_sentence(item) or item for item in contract_terms[:6]]
    )
    service_spec_rows = _build_supply_rows(documents)
    return {
        "overview": overview[:6],
        "compliance_highlights": compliance_highlights[:6],
        "delivery_model": delivery_model[:6],
        "contract_highlights": contract_terms[:6],
        "next_actions": next_actions[:4],
        "extracted_fields": extracted_fields[:8],
        "procurement_kind": procurement_kind,
        "supply_section_note": "Позиции объекта закупки собраны из технических документов и приложений."
        if service_spec_rows
        else "Структурированные позиции объекта закупки не выделены автоматически. Нужна ручная сверка ТЗ и приложений.",
        "spec_table": {
            "columns": [
                "№",
                "Наименование",
                "Кол-во",
                "Ед. изм.",
                "Характеристики",
                "Источник",
            ],
            "rows": service_spec_rows,
        },
    }
