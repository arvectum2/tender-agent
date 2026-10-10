"""Product-owned requirement row projection for operator reports.

Rows retain explicit deterministic/fallback-adapter attribution. Text is
translated for display, never asserted to be a verified original EIS fact.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def normalize_requirement_title(title: str, procurement_kind: str, *, translate: Callable[[str], str]) -> str | None:
    translated = translate(title)
    if procurement_kind != "services":
        return translated
    service_specific = {
        "Требуется соответствие указанным техническим стандартам.": "Услуги должны соответствовать требованиям технического задания и обязательным нормативам.",
        "Оборудование и товары должны соответствовать заявленной спецификации.": "Услуги должны быть оказаны в полном объеме и в соответствии с техническим заданием.",
        "Нужно пройти приёмочные испытания по условиям договора.": "Приемка услуг проводится по условиям контракта.",
        "Требуются гарантия и поддержка после поставки.": "Исполнитель должен обеспечить качественное оказание услуг и выдать предусмотренные итоговые документы.",
        "Техническое предложение со спецификацией.": "Описание программы, графика и состава оказываемых услуг.",
        "Декларация о соответствии.": "Документы, подтверждающие соответствие обязательным требованиям закупки.",
    }
    return service_specific.get(translated, translated)


def extract_requirement_rows(requirements: dict[str, Any], core_complete: bool, procurement_kind: str, *, translate: Callable[[str], str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for title in requirements.get("technical_requirements", []):
        normalized_title = normalize_requirement_title(title, procurement_kind, translate=translate)
        if not normalized_title:
            continue
        rows.append(
            {
                "title": normalized_title,
                "detail": "Извлечено детерминированным адаптером из доступных документов.",
                "source": "адаптер раннера" if core_complete else "fallback-адаптер",
            }
        )
    for title in requirements.get("document_requirements", []):
        normalized_title = normalize_requirement_title(title, procurement_kind, translate=translate)
        if not normalized_title:
            continue
        rows.append(
            {
                "title": normalized_title,
                "detail": "Требование к комплекту документов или подтверждению квалификации.",
                "source": "адаптер раннера" if core_complete else "fallback-адаптер",
            }
        )
    return rows[:10]
