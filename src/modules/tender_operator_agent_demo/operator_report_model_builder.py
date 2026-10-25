"""Product-owned procurement report model assembly, dependency-injected.

No ingestion or platform internals; legal/commercial unknowns remain explicit.
Original projection body preserved verbatim for parity.
"""
from __future__ import annotations

from typing import Any


def build_procurement_report_model(
    metadata: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
    *,
    repository_sha: str = "unknown",
    _item_rows: Any,
    _procurement_volume_status: Any,
    _public_document_inventory: Any,
    _format_source_location: Any,
    UNKNOWN: Any,
    _customer_display_name: Any,
    _parse_timestamp: Any,
    _number: Any,
    _russian_datetime: Any,
    _format_okpd2_codes: Any,
) -> dict[str, Any]:
    requirements = outputs["requirements"]
    preliminary = requirements.get("preliminary_analysis", {})
    canonical_graph = preliminary.get("canonical_procurement_model") or {}
    context = requirements.get("analysis_context", {})
    recommendation = outputs["final_recommendation"]
    risks = outputs["contract_risks"].get("risks", [])
    economics = outputs["economics"]
    items = _item_rows(preliminary)
    scope = context.get("procurement_scope", {})
    if scope.get("scope_classification_conflict"):
        for row in items:
            row["quality_gate_status"] = "scope_classification_conflict"
    procurement = metadata.get("procurement") or {}
    volume_status, volume_status_reason = _procurement_volume_status(items, context.get("procurement_category"))
    if scope.get("scope_classification_conflict"):
        volume_status, volume_status_reason = "scope_conflict", "Тип закупки определён неоднозначно. Товарная часть требует проверки."
    raw_okpd2 = context.get("okpd2_codes") or metadata.get("okpd2_codes") or procurement.get("okpd2_codes", [])
    okpd2_codes = [dict(item, evidence_ids=item.get("evidence_ids") or ["eis_notice:okpd2_codes"]) for item in raw_okpd2 if item.get("code")]
    needs_review_reasons = [reason for reason in recommendation.get("rationale", []) if "неизвестен фактический объём" not in reason.lower()]
    if volume_status != "known":
        needs_review_reasons.append("Неизвестен фактический объём")
    missing_contract = "draft_contract" in context.get("missing_documents", preliminary.get("missing_documents", []))
    blockers = ["Отсутствует проект контракта"] if missing_contract else []
    source_documents = _public_document_inventory(metadata)
    evidence_map = [
        {
            "document": "Извещение о закупке",
            "row": _format_source_location(row["source_row"]),
            "document_type": "извещение",
            "related_items": [row["stable_item_id"]],
        }
        for row in items for evidence_id in row["evidence_ids"]
    ]
    for risk_index, risk in enumerate(risks, start=1):
        for locator_index, locator in enumerate(risk.get("evidence_locators", []), start=1):
            if not isinstance(locator, dict) or not locator.get("document") or not locator.get("locator"):
                continue
            evidence_map.append({
                "document": locator["document"],
                "row": _format_source_location(locator["locator"]),
                "document_type": "документ закупки",
                "related_items": [],
            })
    subject = context.get("procurement_subject") or metadata.get("procurement_title") or procurement.get("procurement_subject") or metadata.get("tender_title") or UNKNOWN
    nmck = context.get("nmck") or (metadata.get("procurement") or {}).get("initial_price")
    publication_datetime = metadata.get("publication_date") or procurement.get("publication_date")
    application_deadline = metadata.get("deadline") or procurement.get("deadline")
    analysis_as_of = metadata.get("analysis_completed_at") or metadata.get("prepared_at") or metadata.get("created_at")
    currency = context.get("currency", "RUB")
    customer_name = _customer_display_name(context.get("customer_name") or metadata.get("customer_name") or procurement.get("customer_name"))
    delivery_place = context.get("delivery_place") or metadata.get("delivery_place") or procurement.get("delivery_place") or UNKNOWN
    contract_draft_status = context.get("contract_draft_status") or ("absent" if missing_contract else "unknown")
    coverage = preliminary.get("item_coverage", {})
    economics_lines = [f"{item.get('label')}: {item.get('value')}" for item in economics.get("metrics", [])]
    for spec_row in preliminary.get("spec_table", {}).get("rows", []):
        if spec_row.get("Сумма, руб.") not in (None, "", "—"):
            economics_lines.append(f"Сумма по исходной строке: {spec_row['Сумма, руб.']}")
    canonical_run_status = canonical_graph.get("run_status")
    decision = (
        "Требуется ручная проверка перед коммерческим расчётом" if canonical_run_status == "needs_review"
        else "Анализ завершён с подтверждёнными ограничениями источников" if canonical_run_status == "completed_with_warnings"
        else "Анализ завершён"
    )
    has_technical_document = any(item["type"] == "технический документ" for item in source_documents)
    confirmed = [
        "предмет закупки, заказчик, сроки подачи и НМЦК",
        "позиция и количество — в извещении",
    ]
    unevaluated = []
    if contract_draft_status == "absent":
        unevaluated.append("порядок оплаты, штрафы, обеспечение, приёмка, расторжение и ответственность сторон")
    if not has_technical_document:
        unevaluated.append("детальные технические характеристики товара: отдельное ТЗ или описание объекта закупки не найдено")
    parsed_as_of, parsed_deadline = _parse_timestamp(analysis_as_of), _parse_timestamp(application_deadline)
    deadline_status_unknown = parsed_as_of is None or parsed_deadline is None
    deadline_expired = bool(not deadline_status_unknown and parsed_as_of > parsed_deadline)
    deadline_status = "unknown" if deadline_status_unknown else ("expired" if deadline_expired else "open")
    recommendation_label = "Статус срока подачи не определён" if deadline_status_unknown else ("Срок подачи заявок истёк" if deadline_expired else ("Требуется проверка" if unevaluated else "Участвовать"))
    unit_economics = None
    total = _number(nmck)
    tonne_quantity = sum(_number(item.get("quantity")) or 0 for item in items if str(item.get("unit_normalized") or item.get("unit_original") or "").lower() in {"т", "тонна", "тонны"})
    if total is not None and tonne_quantity > 0:
        unit_economics = {"unit": "тонну", "value": round(total / tonne_quantity, 2)}
    return {
        "metadata": {
            "procurement_number": metadata.get("procurement_id"), "report_id": f"report-{metadata.get('run_id')}",
            "report_version": "r1-canonical-v1", "locale": "ru-RU", "source_set_version": "current-run",
            "extraction_version": "r1-b2", "analysis_version": "r1-b3", "repository_sha": repository_sha,
            "document_count": len(metadata.get("files", [])), "service_item_count": len(items),
            "analyzed_item_count": coverage.get("analyzed_item_count", len(items)),
            "decision_status": canonical_run_status or recommendation.get("recommendation", "needs_review"),
            "degraded_mode": metadata.get("analysis_mode") == "fallback_deterministic_adapter",
            "completeness_status": context.get("document_coverage", "partial"),
        },
        "ai_runtime_provenance": metadata.get("ai_runtime_provenance", {}),
        "procurement_number": metadata.get("procurement_id") or UNKNOWN,
        "procurement_title": subject,
        "publication_datetime": publication_datetime or UNKNOWN,
        "application_deadline": application_deadline or UNKNOWN,
        "analysis_as_of": _russian_datetime(analysis_as_of),
        "analysis_as_of_iso": parsed_as_of.isoformat() if parsed_as_of else None,
        "deadline_status": deadline_status,
        "publication_datetime_display": _russian_datetime(publication_datetime),
        "application_deadline_display": _russian_datetime(application_deadline),
        "decision": decision,
        "nmck": nmck if nmck is not None else UNKNOWN,
        "currency": currency,
        "line_items": items,
        "customer_documents": source_documents,
        "customer_decision": {
            "recommendation": recommendation_label,
            "reasons": (["В документах подтверждены основные реквизиты закупки и объём позиции."] + (["Проект контракта не найден в предоставленном комплекте."] if contract_draft_status == "absent" else []) + (["Отдельное ТЗ или описание объекта закупки не найдено."] if not has_technical_document else [])),
            "confirmed": confirmed,
            "not_evaluated": unevaluated,
            "next_action": "Указать подтверждённое время завершения анализа или срок подачи заявок для определения статуса." if deadline_status_unknown else ("Искать повторную или аналогичную закупку; этот отчёт использовать только для ретроспективного анализа." if deadline_expired else "Сначала необходимо запросить отсутствующие документы. Предметные вопросы по договорным и техническим условиям будут сформированы после их получения."),
        },
        "unit_economics": unit_economics,
        "corpus_limitations": (["Проект контракта не найден в предоставленном комплекте из пяти документов. Невозможно оценить порядок оплаты, штрафы, обеспечение, приёмку, расторжение и ответственность сторон."] if contract_draft_status == "absent" else []) + (["Отдельное техническое задание или описание объекта закупки не найдено в предоставленном комплекте; детальные характеристики товара не извлечены."] if not has_technical_document else []),
        "field_evidence": metadata.get("_field_evidence", {}),
        "customer_name": customer_name,
        "customer_inn": context.get("customer_inn") or metadata.get("customer_inn") or procurement.get("customer_inn"),
        "customer_kpp": context.get("customer_kpp") or metadata.get("customer_kpp") or procurement.get("customer_kpp"),
        "delivery_place": delivery_place,
        "delivery_address": context.get("delivery_address") or delivery_place,
        "delivery_region": context.get("delivery_region"),
        "delivery_status": context.get("delivery_status") or "unknown",
        "delivery_evidence_ids": context.get("delivery_evidence_ids", []),
        "contract_draft_status": contract_draft_status,
        "procurement_scope": scope,
        "contract_draft_documents": context.get("contract_draft_documents", []),
        "contract_draft_evidence_ids": context.get("contract_draft_evidence_ids", []),
        "executive_summary": {
            "subject": subject, "nmck": nmck if nmck is not None else UNKNOWN, "currency": currency,
            "service_item_count": len(items), "analyzed_item_count": coverage.get("analyzed_item_count", len(items)),
            "decision": decision,
            "rationale": needs_review_reasons, "blockers": blockers,
            "next_action": (preliminary.get("next_actions") or [UNKNOWN])[0],
            "source_coverage": context.get("document_coverage", "partial"), "overall_confidence": "low" if missing_contract else "medium",
        },
        "document_coverage": {"discovered": len(metadata.get("files", [])), "parsed": len(metadata.get("files", [])), "missing": ["Проект контракта"] if contract_draft_status == "absent" else [], "warnings": context.get("extraction_warnings", []), "impact": "Договорный анализ ограничен" if contract_draft_status in {"absent", "parse_failed", "unknown"} else ""},
        "procurement_passport": {"subject": subject, "title": subject, "publication_datetime": publication_datetime or UNKNOWN, "application_deadline": application_deadline or UNKNOWN, "category": context.get("procurement_category"), "domain": context.get("domain"), "okpd2": "; ".join(_format_okpd2_codes(okpd2_codes)) if okpd2_codes else (context.get("okpd2") or "не указан в доступном извещении"), "nmck": nmck if nmck is not None else UNKNOWN, "currency": currency, "customer": customer_name, "delivery_place": delivery_place, "contract_draft_status": contract_draft_status},
        "okpd2_codes": okpd2_codes,
        "procurement_volume_status": volume_status,
        "volume_status_reason": volume_status_reason,
        "needs_review_reasons": needs_review_reasons,
        "service_catalog": items,
        "requirements": requirements.get("requirements", []),
        "contract_conditions": {"status": contract_draft_status, "unknown_fields": context.get("unknown_contract_terms", []), "reason": "Проект контракта приложен, но автоматически разобрать его не удалось" if contract_draft_status == "parse_failed" else ("Проект контракта отсутствует" if contract_draft_status == "absent" else "Требуется ручная проверка")},
        "timeline": {"value": application_deadline, "status": "known" if application_deadline else "unknown"},
        "economics": {"known_inputs": economics.get("metrics", []), "unknown_inputs": (["себестоимость", "supplier profile"] if volume_status == "known" else ["фактический объём", "себестоимость", "supplier profile"]), "unavailable_calculations": ["выручка", "прибыль", "маржа", "рентабельность"], "warnings": economics.get("warnings", [])},
        "risks": risks,
        "contradictions": [],
        "missing_data": [{"importance": "blocking", "description": "Проект контракта отсутствует", "why_needed": "Без него неизвестны оплата, приемка, штрафы и обеспечение", "required_action": "Получить проект контракта", "decision_effect": "Блокирует безусловное GO"}] if contract_draft_status == "absent" else [],
        "customer_questions": outputs["supplier_questions"].get("questions", []),
        "bid_decision": {"status": "needs_review", "rationale": needs_review_reasons, "blockers": blockers, "conditions": ["Получить проект контракта", "Подтвердить ресурсы и себестоимость"], "assumptions": [], "confidence": "low" if missing_contract else "medium", "next_action": (preliminary.get("next_actions") or [UNKNOWN])[0], "evidence_ids": []},
        "action_plan": preliminary.get("next_actions", []), "evidence_map": evidence_map,
        "limitations": (["Проект контракта приложен, но автоматически разобрать его не удалось"] if contract_draft_status == "parse_failed" else []) + ([] if volume_status == "known" else ["Неизвестен фактический объём"]) + ["Нет supplier profile", "Нет подтверждённой собственной себестоимости", "Прибыль и маржа не рассчитываются"],
        "provenance": {"run_id": metadata.get("run_id"), "source": metadata.get("procurement_source"), "report_model": "canonical", "production_model_hash": canonical_graph.get("production_model_hash")},
        "compatibility_sections": {
            "report_title": "Отчёт по загруженному прогону тендерного агента",
            "notice_number": metadata.get("procurement_id"),
            "procurement_title": subject,
        "publication_datetime": _russian_datetime(publication_datetime),
        "application_deadline": _russian_datetime(application_deadline),
        "analysis_as_of": _russian_datetime(analysis_as_of),
        "deadline_expired": deadline_expired,
            "line_items": items,
            "positions_count": len(items),
            "source_status": "Документы получены через ЕИС" if metadata.get("procurement_source") else "Документы загружены вручную",
            "preliminary_overview": preliminary.get("overview", []),
            "spec_columns": preliminary.get("spec_table", {}).get("columns", []),
            "spec_rows": preliminary.get("spec_table", {}).get("rows", []),
            "quotes": outputs["quotes_comparison"].get("highlights", []),
            "economics": economics_lines,
            "contract_highlights": preliminary.get("contract_highlights", []),
            "downloaded_files_count": metadata.get("downloaded_files_count", len(metadata.get("files", []))),
            "archive_available": bool(metadata.get("archive_downloaded")),
        },
    }
