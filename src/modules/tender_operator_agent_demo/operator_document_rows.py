"""Pure procurement product projections; source-oriented only."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def extract_meaningful_snippets(
    text: str, keywords: tuple[str, ...], *, max_snippets: int = 8
) -> list[str]:
    if not text:
        return []
    snippets: list[str] = []
    seen: set[str] = set()
    normalized_text = re.sub(r"\s+", " ", text)
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), normalized_text, re.IGNORECASE):
            start = max(0, match.start() - 120)
            end = min(len(normalized_text), match.end() + 220)
            snippet = normalized_text[start:end].strip(" .;,\n\t")
            if len(snippet) < 40:
                continue
            key = snippet.lower()
            if key in seen:
                continue
            seen.add(key)
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def build_software_work_rows(
    documents: list[AnalyzedDocument],
    *,
    _cleanup_tabular_value,
    _document_source_label,
    _extract_meaningful_snippets,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    candidate_docs = [
        doc
        for doc in documents
        if doc.text
        and (
            doc.role == "technical_spec"
            or "описание объекта" in doc.display_name.lower()
            or "техничес" in doc.display_name.lower()
        )
    ]
    block_definitions = [
        (
            "Новые структурированные электронные медицинские документы",
            ("структурированных электронных медицинских документ", "сэмд"),
            "Разработать и внедрить новые структуры/формы электронных медицинских документов.",
            "ПК «Здравоохранение», медицинская информационная система",
            "Обновленный модуль с поддержкой новых СЭМД",
            "Приемка по реализованным структурам документов и результатам тестирования",
        ),
        (
            "Обработка информации об ИПРА",
            ("ипра", "реабилитации и абилитации"),
            "Реализовать обработку данных индивидуальных программ реабилитации и абилитации.",
            "ПК «Здравоохранение», внешние данные ИПРА",
            "Система обрабатывает и хранит сведения ИПРА в требуемом формате",
            "Приемка по корректной обработке сценариев и данным ИПРА",
        ),
        (
            "Интеграция с ЕРН через СМЭВ",
            ("ерн", "смэв", "межведомственного электронного взаимодействия"),
            "Настроить обмен данными и интеграционный контур с ЕРН через СМЭВ.",
            "ЕРН, СМЭВ, ПК «Здравоохранение»",
            "Рабочая интеграция и обмен данными с внешним регистром",
            "Приемка по интеграционному тестированию и доступности обмена",
        ),
        (
            "Получение данных об участниках СВО",
            ("сво", "витрины данных министерства обороны", "статуса сво"),
            "Реализовать получение и обработку данных об участниках СВО из внешней витрины.",
            "Витрина данных Минобороны, ПК «Здравоохранение»",
            "Обогащение записей пациентов данными по статусу СВО",
            "Приемка по корректному получению, кэшированию и журналированию данных",
        ),
        (
            "Передача лицензии на обновленный модуль",
            ("лиценз", "передаче лицензии", "передача прав"),
            "Передать заказчику лицензию и права использования обновленного модуля.",
            "Документы на лицензирование, обновленный модуль",
            "Заказчик получает правоомерное использование обновленного решения",
            "Приемка по передаче лицензии и комплекту закрывающих документов",
        ),
    ]
    for title, keywords, action, systems, result, acceptance in block_definitions:
        matched_doc = None
        matched_snippet = None
        for doc in candidate_docs:
            snippets = _extract_meaningful_snippets(
                doc.text or "", keywords, max_snippets=1
            )
            if snippets:
                matched_doc = doc
                matched_snippet = snippets[0]
                break
        if not matched_doc:
            continue
        rows.append(
            {
                "№": str(len(rows) + 1),
                "Блок работ / результат": title,
                "Что нужно сделать": action,
                "Входные/внешние системы": systems,
                "Результат для заказчика": result,
                "Критерии приёмки": acceptance
                if not matched_snippet
                else _cleanup_tabular_value(matched_snippet[:220]) or acceptance,
                "Источник": _document_source_label(matched_doc),
            }
        )
    return rows
