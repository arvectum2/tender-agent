"""Product-owned RFQ and document-grounded requirement projections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.modules.tender_operator_agent_demo.operator_risk_report import (
    build_document_grounded_risks,
)

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def build_goods_rfq_payload(
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    *,
    _collect_goods_supply_items_from_documents,
) -> dict[str, Any]:
    items = _collect_goods_supply_items_from_documents(documents)
    return {
        "rfq_title": f"RFQ draft / {metadata['tender_title']}",
        "sections": [
            "Позиции поставки и объём",
            "Подтверждение ГОСТ, сертификатов и паспортов качества",
            "Срок поставки, наличие на складе и логистика",
            "Цена за единицу, сумма, НДС и срок действия КП",
        ],
        "items": [
            {
                "№": item.item_no or "—",
                "Позиция": item.name,
                "Кол-во": item.quantity or "не указано",
                "Ед.": item.unit or "—",
                "Обязательные характеристики": "; ".join(item.characteristics)
                if item.characteristics
                else "Сверить по ТЗ",
                "ГОСТ / норматив": ", ".join(item.gost) if item.gost else "—",
                "Цена за ед.": item.unit_price or "",
                "Сумма": item.total_price or "",
                "Срок поставки": "",
                "Сертификаты / паспорт": "",
                "Отклонения / аналоги": "Допустим эквивалент"
                if item.equivalent_allowed
                else "",
            }
            for item in items
        ],
    }


def build_document_grounded_requirements(
    documents: list[AnalyzedDocument],
    procurement_kind: str,
    *,
    _build_goods_requirement_rows,
    _cleanup_tabular_value,
    _extract_meaningful_snippets,
) -> list[dict[str, str]]:
    if procurement_kind in {"services", "rental", "works", "unresolved"}:
        return []
    if procurement_kind == "goods":
        rows = _build_goods_requirement_rows(documents)
        if rows:
            return rows
    rows: list[dict[str, str]] = []
    for doc in documents:
        text = doc.text or ""
        if not text:
            continue
        doc_name = doc.display_name
        if procurement_kind in {
            "mixed",
            "software_modification",
            "integration",
            "license",
        }:
            mapping = [
                (
                    ("модификац", "программного комплекса", "модул"),
                    "Модификация ПК «Здравоохранение»",
                    "функциональное",
                    "high",
                ),
                (
                    ("структурированных электронных медицинских документ", "сэмд"),
                    "Разработка новых структурированных электронных медицинских документов",
                    "функциональное",
                    "high",
                ),
                (
                    ("ипра", "реабилитации и абилитации"),
                    "Обработка информации об ИПРА",
                    "функциональное",
                    "high",
                ),
                (
                    ("ерн", "смэв"),
                    "Интеграция с ЕРН через СМЭВ",
                    "интеграционное",
                    "high",
                ),
                (
                    ("сво", "витрины данных министерства обороны"),
                    "Получение данных об участниках СВО из витрины Минобороны",
                    "интеграционное",
                    "high",
                ),
                (
                    ("лиценз", "передаче лицензии", "передача прав"),
                    "Передача лицензии и прав на обновленный модуль",
                    "лицензионное",
                    "high",
                ),
                (
                    ("приемк", "испытан", "акт"),
                    "Требования к приемке результатов работ",
                    "приёмка",
                    "medium",
                ),
                (
                    ("срок", "этап"),
                    "Сроки и этапность выполнения работ",
                    "срок / этап",
                    "medium",
                ),
                (
                    ("заявк", "инструкц"),
                    "Требования к заявке участника",
                    "заявка участника",
                    "medium",
                ),
                (
                    ("персональн", "медицинск"),
                    "Требования к обработке медицинских и персональных данных",
                    "информационная безопасность / персональные данные",
                    "medium",
                ),
            ]
        else:
            mapping = [
                (
                    ("поставка", "товар"),
                    "Требования к предмету поставки",
                    "функциональное",
                    "high",
                ),
                (
                    ("приемк", "испытан", "акт"),
                    "Требования к приемке",
                    "приёмка",
                    "medium",
                ),
                (("срок",), "Сроки исполнения", "срок / этап", "medium"),
            ]
        for keywords, title, req_type, priority in mapping:
            snippets = _extract_meaningful_snippets(text, keywords, max_snippets=1)
            if not snippets:
                continue
            if any(
                item["title"] == title and item["source"] == doc_name for item in rows
            ):
                continue
            rows.append(
                {
                    "title": title,
                    "detail": _cleanup_tabular_value(snippets[0][:260]) or title,
                    "source": doc_name,
                    "type": req_type,
                    "priority": priority,
                }
            )
    return rows[:12]


def build_document_grounded_questions(
    procurement_kind: str,
    documents: list[AnalyzedDocument],
    *,
    _build_goods_questions,
    _collect_supply_items,
    _is_vehicle_maintenance_services,
    _service_okpd2_from_sources,
) -> list[str]:
    if procurement_kind in {"mixed", "software_modification", "integration", "license"}:
        return [
            "Есть ли у исполнителя опыт доработки медицинских информационных систем и аналогичных госинтеграций?",
            "Есть ли подтвержденный опыт интеграции через СМЭВ и подключения внешних реестров?",
            "Кто предоставляет доступы и тестовые контуры ЕРН, СМЭВ и витрины данных Минобороны?",
            "Доступны ли форматы обмена, спецификации API и правила согласования СЭМД?",
            "Входит ли в объем работ интеграционное тестирование и сопровождение приемки?",
            "Какие результаты передаются заказчику: код, модуль, лицензия, документация, инструкции?",
            "Как оформляется передача лицензии и прав на обновленный модуль?",
            "Какие ограничения и риски есть по персональным данным, медданным и защищенным каналам?",
        ]
    if procurement_kind == "goods":
        return _build_goods_questions(documents)
    service_text = "\n".join(doc.text or "" for doc in documents)
    if procurement_kind == "services" and _is_vehicle_maintenance_services(
        service_text,
        _service_okpd2_from_sources(service_text, documents),
        _collect_supply_items(documents),
    ):
        return [
            "Предоставьте проект контракта для проверки оплаты, приемки, ответственности, обеспечения, сроков и расторжения.",
            "Какова подтверждённая внутренняя стоимость нормо-часа и какие затраты включены в нее?",
            "Какие услуги из перечня выполняются собственными силами, а для каких требуется подрядчик?",
            "Подтверждены ли специалисты, оборудование и ремонтная база для полного перечня операций?",
            "Как учитываются запасные части и материалы, если это не раскрыто документацией?",
            "Можно ли сопоставить каждую релевантную единичную расценку с подтверждённой себестоимостью?",
        ]
    return [
        "Подтверждаете ли вы исполнение требований технического задания в полном объеме?",
        "Какие сроки исполнения и ограничения по поставке/работам вы видите?",
        "Какие документы и подтверждения должны быть подготовлены для заявки?",
    ]


def project_document_grounded_risks(
    procurement_kind: str,
    documents: list[AnalyzedDocument],
    contract_text: str,
    *,
    _collect_supply_items,
    _is_vehicle_maintenance_services,
    _service_okpd2_from_sources,
) -> list[dict[str, str]]:
    return build_document_grounded_risks(
        procurement_kind,
        documents,
        contract_text,
        detect_maintenance=_is_vehicle_maintenance_services,
        source_okpd2=_service_okpd2_from_sources,
        collect_items=_collect_supply_items,
    )
