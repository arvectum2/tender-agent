"""Pure procurement product projections; source-oriented only."""

from __future__ import annotations

import re


def extract_legacy_goods_spec_rows(
    technical_spec_text: str,
    *,
    _cleanup_tabular_value,
    _extract_goods_characteristics,
    _extract_gost_tokens,
    _normalize_quantity_value,
) -> list[dict[str, str]]:
    if not technical_spec_text:
        return []
    unit_pattern = r"(шт|м|компл(?:ект)?|упак(?:овка)?|пара|кг|л|рул(?:он)?|набор|ед\.?|усл\.?\s*ед\.?|услуга)"
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    section_pattern = re.compile(
        r"(?:(?P<section_no>\d(?:\s*\d)?)\.\s*)?Описание\s+объекта\s+закупки:",
        re.IGNORECASE,
    )
    matches = list(section_pattern.finditer(technical_spec_text))
    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(technical_spec_text)
        )
        section = technical_spec_text[start:end]
        section_number = re.sub(r"\s+", "", match.group("section_no") or "") or str(
            len(rows) + 1
        )
        row_match = re.search(
            r"1\s+2\s+3\s+4\s+5\s+6\s+7\s+(?P<row>.+?)(?=Характеристики\s+объекта\s+закупки:|$)",
            section,
            re.IGNORECASE | re.DOTALL,
        )
        if not row_match:
            continue
        row_text = _cleanup_tabular_value(row_match.group("row")) or ""
        parsed_match = re.search(
            rf"(?P<num>\d+)\s+(?P<name>.+?)\s+(?P<unit>{unit_pattern})\s+(?P<tail>.+)$",
            row_text,
            re.IGNORECASE,
        )
        if not parsed_match:
            continue
        tail = _cleanup_tabular_value(parsed_match.group("tail")) or ""
        quantity_match = re.search(r"(\d+(?:[.,]\d+)?)\s*$", tail)
        quantity = (
            _normalize_quantity_value(
                quantity_match.group(1) if quantity_match else "не указано"
            )
            or "не указано"
        )
        characteristics = (
            _extract_goods_characteristics(section)
            or "Требуется сверка характеристик по ТЗ."
        )
        row = {
            "№": section_number or parsed_match.group("num"),
            "Наименование": _cleanup_tabular_value(parsed_match.group("name"))
            or "Позиция",
            "Кол-во": quantity,
            "Ед. изм.": _cleanup_tabular_value(parsed_match.group("unit")) or "—",
            "Ключевые характеристики": characteristics,
            "ГОСТ / норматив": ", ".join(_extract_gost_tokens(section)) or "—",
            "Эквивалент": "нет",
            "Цена за ед., руб.": "—",
            "Сумма, руб.": "—",
            "Источник": "Техническое задание",
        }
        key = (
            row["Наименование"].lower(),
            row["Ед. изм."].lower(),
            row["Кол-во"].lower(),
            row["Ключевые характеристики"].lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows
