"""Bounded product-side XLSX/NMCK goods rows.

No EIS authenticity is inferred here: tabular cells become candidate positions,
and uncertain layouts are excluded rather than converted to source facts.
All legacy parsing primitives are injected; the Data Platform remains separate.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import TypeVar

TItem = TypeVar("TItem")


def extract_supply_items_from_xlsx_text(
    text: str,
    source_document: str,
    *,
    supply_item_type: type[TItem],
    supply_unit_pattern: re.Pattern[str],
    _cleanup_tabular_value: Callable[[str | None], str | None],
    _is_line_item_name: Callable[[str | None], bool],
    _parse_float: Callable[[str | None], float | None],
    _is_ktru_or_okpd: Callable[[str | None], bool],
    _split_trailing_classification: Callable[
        [str | None], tuple[str | None, str | None, str | None]
    ],
    _normalize_quantity_value: Callable[[str | None], str | None],
    _normalize_supply_name: Callable[[str | None], str],
    _normalize_supply_unit: Callable[[str | None], str | None],
    _extract_gost_tokens: Callable[[str], list[str]],
    _format_decimal_price: Callable[[float | None], str | None],
) -> list[TItem]:
    if not text or "\t" not in text:
        return []
    items: list[TItem] = []
    column_map: dict[str, int] = {}
    for line in text.splitlines():
        cells = [_cleanup_tabular_value(cell) or "" for cell in line.split("\t")]
        meaningful = [cell for cell in cells if cell]
        if len(meaningful) < 4:
            continue
        lowered = " ".join(meaningful).lower()
        if "есклп" in lowered and "колич" in lowered:
            # Wrapped XLSX headers for medicinal products are emitted on two
            # lines; their labels are shifted left by one cell after export.
            column_map.update({"name": 1, "identifier": 2, "unit": 3, "quantity": 12})
            continue
        if ("наимен" in lowered or "мнн" in lowered) and (
            "колич" in lowered or "кол-во" in lowered
        ):
            for index, cell in enumerate(cells):
                cell_lower = cell.lower()
                if "наимен" in cell_lower or "мнн" in cell_lower:
                    column_map["name"] = index
                elif "колич" in cell_lower or "кол-во" in cell_lower:
                    column_map["quantity"] = index
                elif "ед." in cell_lower or "единиц" in cell_lower:
                    column_map["unit"] = index
                elif any(marker in cell_lower for marker in ("ктру", "окпд", "есклп")):
                    column_map["identifier"] = index
            continue
        if any(
            token in lowered
            for token in (
                "используемый метод",
                "коммерческие предложения",
                "коэффициент",
            )
        ):
            continue
        # "лист"/"sheet" skip workbook page headers, but only as standalone
        # words: a substring match would discard products such as
        # "Разделитель листов" whose name merely contains those letters.
        if re.search(r"(?<!\w)(лист|sheet)(?!\w)", lowered):
            continue
        if "наименование" in lowered and ("коли" in lowered or "кол-во" in lowered):
            continue
        if not re.fullmatch(r"\d{1,3}", meaningful[0]):
            continue
        if {"name", "unit", "quantity"}.issubset(column_map):
            raw_name = (
                cells[column_map["name"]] if column_map["name"] < len(cells) else ""
            )
            unit_raw = (
                cells[column_map["unit"]] if column_map["unit"] < len(cells) else ""
            )
            quantity_raw = (
                cells[column_map["quantity"]]
                if column_map["quantity"] < len(cells)
                else ""
            )
            if (
                not _is_line_item_name(raw_name)
                or not supply_unit_pattern.fullmatch(unit_raw)
                or _parse_float(quantity_raw) is None
            ):
                continue
            identifier_index = column_map.get("identifier")
            ktru = (
                cells[identifier_index]
                if identifier_index is not None and identifier_index < len(cells)
                else None
            )
            okpd2 = None
            if not _is_ktru_or_okpd(ktru):
                ktru = None
                clean_name, suffix_ktru, suffix_okpd2 = _split_trailing_classification(
                    raw_name
                )
                if suffix_ktru is not None or suffix_okpd2 is not None:
                    raw_name = clean_name
                    ktru, okpd2 = suffix_ktru, suffix_okpd2
            numeric_tail = [
                _parse_float(value)
                for value in cells[column_map["quantity"] + 1 :]
                if value
            ]
            numeric_tail = [value for value in numeric_tail if value is not None]
            total_value = numeric_tail[-1] if numeric_tail else None
            quantity = _normalize_quantity_value(quantity_raw)
            item = supply_item_type(
                item_no=meaningful[0],
                name=_normalize_supply_name(raw_name),
                quantity=quantity,
                unit=_normalize_supply_unit(unit_raw),
                characteristics=[],
                gost=_extract_gost_tokens(" ".join(meaningful)),
                equivalent_allowed="эквивалент" in raw_name.lower(),
                source_document=source_document,
                source_kind="nmck_xlsx",
                confidence="high",
                raw_fragment=line,
                total_price=_format_decimal_price(total_value),
                source_documents=[source_document],
                quantity_status="specified",
                source_row_number=len(items) + 1,
                evidence_id=f"ev-{hashlib.sha256(f'{source_document}|xlsx|{len(items) + 1}|{raw_name}|{quantity}|{unit_raw}'.encode()).hexdigest()[:16]}",
                ktru=ktru,
                okpd2=okpd2,
            )
            items.append(item)
            continue
        raw_name = meaningful[1]
        value_offset = 2
        ktru = None
        okpd2 = None
        if _is_ktru_or_okpd(meaningful[value_offset]):
            ktru = meaningful[value_offset]
            value_offset += 1
        else:
            # A labelled code embedded in the name cell is fallback evidence
            # only; a dedicated identifier column always takes precedence.
            clean_name, suffix_ktru, suffix_okpd2 = _split_trailing_classification(
                raw_name
            )
            if suffix_ktru is not None or suffix_okpd2 is not None:
                raw_name = clean_name
                ktru, okpd2 = suffix_ktru, suffix_okpd2
        name = _normalize_supply_name(raw_name)
        if not _is_line_item_name(name):
            continue
        if len(meaningful) <= value_offset + 1:
            continue
        unit_raw = meaningful[value_offset]
        quantity_raw = meaningful[value_offset + 1]
        if (
            not supply_unit_pattern.fullmatch(unit_raw)
            or _parse_float(quantity_raw) is None
        ):
            # A table row with shifted/ambiguous columns is review material, not a line item.
            continue
        unit = _normalize_supply_unit(unit_raw)
        quantity = _normalize_quantity_value(quantity_raw)
        numeric_tail = [_parse_float(value) for value in meaningful[value_offset + 2 :]]
        numeric_tail = [value for value in numeric_tail if value is not None]
        total_value = numeric_tail[-1] if numeric_tail else None
        quantity_value = _parse_float(quantity)
        derived_unit_price = (
            (total_value / quantity_value)
            if total_value is not None and quantity_value not in (None, 0)
            else None
        )
        price_value = derived_unit_price or (
            numeric_tail[-2] if len(numeric_tail) >= 2 else None
        )
        item = supply_item_type(
            item_no=meaningful[0],
            name=name,
            quantity=quantity,
            unit=unit,
            characteristics=[],
            gost=_extract_gost_tokens(" ".join(meaningful)),
            equivalent_allowed="эквивалент" in raw_name.lower(),
            source_document=source_document,
            source_kind="nmck_xlsx",
            confidence="high" if total_value is not None else "medium",
            raw_fragment=line,
            unit_price=_format_decimal_price(price_value),
            total_price=_format_decimal_price(total_value),
            source_documents=[source_document],
            quantity_status="specified"
            if quantity is not None and unit
            else "not_specified",
            source_row_number=len(items) + 1,
            evidence_id=f"ev-{hashlib.sha256(f'{source_document}|xlsx|{len(items) + 1}|{name}|{quantity}|{unit}'.encode()).hexdigest()[:16]}",
            ktru=ktru,
            okpd2=okpd2,
        )
        items.append(item)
    return items
