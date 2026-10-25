"""Client-ready operator reports keep evidence limitations but not machine diagnostics."""
from __future__ import annotations

from src.modules.tender_operator_agent_demo.operator_customer_report_language import (
    customer_narrative,
    readable_document_origin,
    readable_document_text_state,
    readable_source,
    sanitize_customer_report_markdown,
)


def test_customer_markdown_hides_internal_machine_codes_not_evidence():
    body = (
        "# Отчёт по загруженному прогону тендерного агента\n\n"
        "- Run ID: toa-run-secret-001\n"
        "- Закупка: Разработка сайта\n"
        "- Заказчик: Государственный музей\n"
        "- Статус: completed_with_warnings\n"
        "- Режим анализа: fallback_deterministic_adapter\n"
        "- Код рекомендации: manual_review_required\n"
        "- Источник: zakupki_gov_ru_getdocs_ip\n"
        "- Статус скачивания: downloaded\n"
        "- Ручная загрузка требовалась: false\n"
        "- техническое задание: original.docx | download=downloaded | text=extracted | source=eis_getdocs_archive\n"
        "## Ручные проверки\n"
        "- Дата окончания подачи: 16.10.2026 10:00 МСК; необходимо проверить редакцию.\n"
        "- getDocsIP no_data: HTTP 409\n"
    )
    result=sanitize_customer_report_markdown(body)
    assert "# Анализ закупки" in result
    assert "Государственный музей" in result
    assert "Дату" not in result or "16.10.2026 10:00 МСК" in result
    assert "16.10.2026 10:00 МСК" in result
    assert "Текст документа доступен для анализа" in result
    assert "Официальный источник ЕИС" in result
    assert "Единая информационная система" in result
    assert "не удалось подтвердить" in result
    for technical in ("Run ID", "getDocsIP", "HTTP 409", "no_data",
                      "fallback_deterministic_adapter", "manual_review_required",
                      "download=", "text=", "source="):
        assert technical not in result


def test_unknown_document_content_not_falsely_reported_as_extracted():
    assert readable_document_text_state("failed") == "Содержание документа требует проверки"
    assert readable_document_text_state("extracted") == "Текст документа доступен для анализа"
    assert readable_document_origin("runtime") == "Источник документа требует уточнения"
    assert readable_source("not-attested-provider") == "Источник требует подтверждения"


def test_model_and_transport_errors_are_not_leaked():
    for value in (
        "ValueError: getDocsIP no_data",
        "Traceback: KeyError inside parsing",
        "JSONDecodeError at source",
        "HTTP 403: archive download failed",
        "fallback_deterministic_adapter",
    ):
        result=customer_narrative(value)
        assert "проверка первоисточника" in result
        assert value not in result
    material="Обеспечение контракта составляет 5% — проверить по исходному договору."
    assert customer_narrative(material) == material
