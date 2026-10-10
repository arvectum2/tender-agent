"""Product-owned conservative risk and request-for-quotation templates.

Templates flag candidate risks for review; they are not verified contract
clauses and must not be interpreted as sourced findings without EIS evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument


def build_document_grounded_risks(
    procurement_kind: str,
    documents: list[AnalyzedDocument],
    contract_text: str,
    *,
    detect_maintenance: Callable[..., bool],
    source_okpd2: Callable[..., str | None],
    collect_items: Callable[..., list[Any]],
) -> list[dict[str, str]]:
    if procurement_kind in {"mixed", "software_modification", "integration", "license"}:
        return [
            {"clause": "Неполные требования к интеграциям", "classification": "deal_breaker_candidate", "impact": "Без описания форматов и сценариев обмена объем работ может быть занижен.", "mitigation": "Запросить спецификации API/СМЭВ и перечень обязательных сценариев обмена."},
            {"clause": "Зависимость от доступов к СМЭВ/ЕРН/витрине Минобороны", "classification": "deal_breaker_candidate", "impact": "Без доступов и тестовых контуров сроки и приемка будут сдвигаться.", "mitigation": "Зафиксировать в переписке и контракте, кто и когда предоставляет доступы и тестовые среды."},
            {"clause": "Риск по персональным и медицинским данным", "classification": "deal_breaker_candidate", "impact": "Ошибки в требованиях ИБ и обработке медданных создают юридический и проектный риск.", "mitigation": "Уточнить требования к ИБ, журналированию, ролям доступа и защите каналов."},
            {"clause": "Неочевидный объем доработок", "classification": "market_standard_harsh_term", "impact": "Фактическая трудоемкость модификации модуля может быть выше, чем следует из краткого описания.", "mitigation": "Разбить оценку по функциональным блокам, этапам и интеграциям до запроса КП."},
            {"clause": "Риск приемки по результатам интеграционного тестирования", "classification": "market_standard_harsh_term", "impact": "Приемка зависит от внешних систем и согласований, не полностью контролируемых исполнителем.", "mitigation": "Зафиксировать критерии приемки, тестовые сценарии и роль заказчика во внешних согласованиях."},
            {"clause": "Риск лицензирования и передачи прав", "classification": "market_standard_harsh_term", "impact": "Неясные условия лицензии и передачи прав могут создать спор по результату работ.", "mitigation": "Проверить проект контракта и приложения на режим лицензии, объем прав и пакет передаваемых материалов."},
        ]
    if procurement_kind == "goods":
        return [
            {"clause": "Несоответствие ГОСТ и характеристикам", "classification": "deal_breaker_candidate", "impact": "Поставка аналога с иными характеристиками приведет к отклонению или проблемам на приемке.", "mitigation": "Запросить производителя, ГОСТ/ТУ и паспорт качества по каждой позиции."},
            {"clause": "Риск по сроку поставки", "classification": "market_standard_harsh_term", "impact": "Товар может не уложиться в срок 15 рабочих дней по заявке.", "mitigation": "Подтвердить складской остаток, срок отгрузки и логистику до адреса заказчика."},
            {"clause": "Логистика и разгрузка не включены в цену", "classification": "market_standard_harsh_term", "impact": "Маржа может снизиться, если доставка, барабаны и разгрузка не учтены.", "mitigation": "Уточнить состав цены и включение доставки/разгрузки в КП."},
            {"clause": "Неполный пакет документов качества", "classification": "market_standard_harsh_term", "impact": "Без сертификатов, деклараций или паспорта качества приемка может быть заблокирована.", "mitigation": "Получить комплект документов качества до подачи или до заключения контракта."},
        ]
    service_text = "\n".join(doc.text or "" for doc in documents)
    if procurement_kind == "services" and detect_maintenance(
        service_text, source_okpd2(service_text, documents), collect_items(documents)
    ):
        service_items = [item for item in collect_items(documents) if item.item_type == "service"]
        evidence = ", ".join(item.evidence_id for item in service_items[:3] if item.evidence_id)
        return [
            {"risk_id": "risk-service-volume", "category": "financial/commercial", "clause": "Неопределённый фактический объём услуг", "classification": "deal_breaker_candidate", "impact": "Единичные расценки не позволяют заранее определить выручку, загрузку и полную себестоимость.", "mitigation": "Получить проект контракта и уточнить порядок заявок; считать экономику только после ввода объёмов и себестоимости.", "evidence_ids": evidence},
            {"risk_id": "risk-service-economics", "category": "financial/commercial", "clause": "Недостаточно данных для расчёта экономики", "classification": "deal_breaker_candidate", "impact": "Нет подтверждённых затрат на труд, материалы, логистику, финансирование и фактический объём.", "mitigation": "Собрать внутреннюю стоимость нормо-часа и коммерческие входы по релевантным операциям.", "evidence_ids": evidence},
            {"risk_id": "risk-service-contract", "category": "source_completeness", "clause": "Неполнота договорного анализа", "classification": "deal_breaker_candidate", "impact": "Без проекта контракта нельзя оценить оплату, приемку, штрафы, обеспечение и часть ответственности.", "mitigation": "Получить и проверить проект контракта до безусловного решения.", "evidence_ids": ""},
            {"risk_id": "risk-service-capability", "category": "operational", "clause": "Операционная возможность требует проверки", "classification": "market_standard_harsh_term", "impact": "Доступные документы не подтверждают наличие специалистов, оборудования и ремонтной базы исполнителя.", "mitigation": "Провести due diligence исполнителя по полному перечню операций.", "evidence_ids": evidence},
            {"risk_id": "risk-service-pricing", "category": "financial/commercial", "clause": "Ценовой риск единичных расценок", "classification": "market_standard_harsh_term", "impact": "Без сравнения с внутренней себестоимостью нельзя оценить выгодность единичных расценок.", "mitigation": "Сопоставить цены строк с подтверждённой себестоимостью до формирования цены заявки.", "evidence_ids": evidence},
        ]
    return [
        {"clause": "Недостаточно предметных данных", "classification": "market_standard_harsh_term", "impact": "Часть рисков требует ручной проверки документов.", "mitigation": "Проверить ТЗ и проект контракта вручную."}
    ]


def build_document_grounded_rfq_sections(procurement_kind: str) -> list[str]:
    if procurement_kind in {"mixed", "software_modification", "integration", "license"}:
        return [
            "Опыт аналогичных доработок медицинских ИС и интеграций",
            "Команда проекта и роли по разработке, интеграции, тестированию и ИБ",
            "Оценка трудоемкости по функциональным блокам и этапам",
            "Подход к интеграции через СМЭВ, ЕРН и витрину Минобороны",
            "Состав передаваемых результатов: модуль, документация, лицензия, права",
            "Стоимость по блокам, тестированию, сопровождению и интеграционным рискам",
        ]
    if procurement_kind == "goods":
        return [
            "Позиции поставки, количество и единицы измерения",
            "Подтверждение характеристик, ГОСТ и допустимости аналогов",
            "Цена за единицу, сумма, НДС и срок действия КП",
            "Срок поставки, наличие на складе, доставка и разгрузка",
            "Сертификаты, декларации и паспорт качества",
        ]
    return [
        "Перечень позиций и объём поставки",
        "Подтверждение сроков, сертификатов и гарантий",
        "Условия оплаты и срок действия КП",
    ]
