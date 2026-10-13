"""Candidate procurement line-item projection from spec, service NMCK and notice XML.

Owned by Tender Agent, not Data Platform: these are procurement-specific
interpretations, not authoritative validation of EIS versions or originals.
Dependencies are passed in explicitly; the legacy public functions stay stable.
"""

from __future__ import annotations

# Exact compatibility extraction: pre-existing B023/SIM102 expressions are intentional.
# ruff: noqa: B023, SIM102
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import TypeVar

TItem = TypeVar("TItem")


def extract_supply_items_from_spec_text(
    text: str,
    source_document: str,
    *,
    supply_item_type: type[TItem],
    supply_unit_pattern: re.Pattern[str],
    _is_goods_supply_table_present: Callable[[str], bool],
    _cleanup_tabular_value: Callable[[str | None], str | None],
    _normalize_supply_name: Callable[[str | None], str],
    _is_line_item_name: Callable[[str | None], bool],
    _normalize_supply_unit: Callable[[str | None], str | None],
    _normalize_quantity_value: Callable[[str | None], str | None],
    _summarize_supply_characteristics: Callable[[list[str]], list[str]],
    _extract_goods_characteristics: Callable[[str], str | None],
    _extract_gost_tokens: Callable[[str], list[str]],
) -> list[TItem]:
    if not text or not _is_goods_supply_table_present(text):
        return []
    lines = [
        _cleanup_tabular_value(line) for line in text.replace("\f", "\n").splitlines()
    ]
    normalized_lines = [line for line in lines if line]
    if not normalized_lines:
        return []

    start_index = 0
    for index, line in enumerate(normalized_lines):
        lowered = line.lower()
        if (
            "№ п/п" in lowered
            or "перечень запасных частей" in lowered
            or "перечень товаров" in lowered
        ):
            start_index = index
            break
    candidate_lines = normalized_lines[start_index:]

    items: list[TItem] = []
    index = 0
    while index < len(candidate_lines):
        line = candidate_lines[index]
        if not re.fullmatch(r"\d{1,3}", line):
            index += 1
            continue
        item_no = line
        if index + 1 >= len(candidate_lines):
            break
        name = _normalize_supply_name(candidate_lines[index + 1])
        if not _is_line_item_name(name):
            index += 1
            continue
        block: list[str] = []
        index += 2
        while index < len(candidate_lines) and not re.fullmatch(
            r"\d{1,3}", candidate_lines[index]
        ):
            block.append(candidate_lines[index])
            index += 1
        equivalent_allowed = (
            "эквивалент"
            in (candidate_lines[index - len(block) - 1] if block else name).lower()
            or "эквивалент" in name.lower()
        )
        unit = None
        quantity = None
        characteristics: list[str] = []
        pos = 0
        while pos < len(block):
            normalized_value = _cleanup_tabular_value(block[pos]) or ""
            next_value = (
                _cleanup_tabular_value(block[pos + 1]) if pos + 1 < len(block) else None
            )
            if (
                not unit
                and supply_unit_pattern.fullmatch(normalized_value)
                and next_value
            ):
                if re.fullmatch(r"\d+(?:[.,]\d+)?", next_value.replace(" ", "")):
                    unit = _normalize_supply_unit(normalized_value)
                    quantity = _normalize_quantity_value(next_value)
                    pos += 2
                    continue
            if (
                normalized_value
                and next_value
                and not re.fullmatch(
                    r"\d+(?:[.,]\d+)?", normalized_value.replace(" ", "")
                )
                and not supply_unit_pattern.fullmatch(normalized_value)
                and not re.fullmatch(r"\d+(?:[.,]\d+)?", next_value.replace(" ", ""))
                and not supply_unit_pattern.fullmatch(next_value)
            ):
                characteristics.append(f"{normalized_value}: {next_value}")
                pos += 2
                continue
            pos += 1
        raw_fragment = "\n".join([item_no, name, *block])
        item = supply_item_type(
            item_no=item_no,
            name=_normalize_supply_name(name),
            quantity=quantity,
            unit=unit,
            characteristics=_summarize_supply_characteristics(
                characteristics or [_extract_goods_characteristics(raw_fragment) or ""]
            ),
            gost=_extract_gost_tokens(raw_fragment),
            equivalent_allowed=equivalent_allowed,
            source_document=source_document,
            source_kind="technical_spec",
            confidence="high" if quantity and unit else "medium",
            raw_fragment=raw_fragment,
            source_documents=[source_document],
            quantity_status="specified"
            if quantity is not None and unit
            else "not_specified",
            source_row_number=len(items) + 1,
            evidence_id=f"ev-{hashlib.sha256(f'{source_document}|spec|{item_no}|{name}|{quantity}|{unit}'.encode()).hexdigest()[:16]}",
        )
        if item.name:
            items.append(item)
    return items


def extract_service_items_from_nmck_text(
    text: str,
    source_document: str,
    *,
    supply_item_type: type[TItem],
    _cleanup_tabular_value: Callable[[str | None], str | None],
    _parse_float: Callable[[str | None], float | None],
    _normalize_supply_name: Callable[[str | None], str],
    _normalize_supply_name_key: Callable[[str | None], str],
    _normalize_supply_unit: Callable[[str | None], str | None],
    _format_decimal_price: Callable[[float | None], str | None],
) -> list[TItem]:
    """Extract unit-priced services from DOCX/XLSX NMCK table text.

    The document extractor preserves DOCX rows as tab-separated text.  Unlike
    goods specifications, an NMCK service list can have no row number and no
    quantity: its rows are name, unit and comparable unit prices.  This parser
    deliberately does not infer a fixed volume or a contract total.
    """
    if not text:
        return []
    rows: list[TItem] = []
    seen: set[tuple[str, str]] = set()
    pending_name: list[str] = []
    for row_number, raw_line in enumerate(text.splitlines(), start=1):
        cells = [_cleanup_tabular_value(cell) or "" for cell in raw_line.split("\t")]
        meaningful = [cell for cell in cells if cell]
        if len(meaningful) < 3:
            pending_lower = meaningful[0].lower() if meaningful else ""
            if (
                len(meaningful) == 1
                and "\t" not in raw_line
                and meaningful[0]
                and not any(
                    marker in pending_lower
                    for marker in (
                        "обоснование",
                        "используемый метод",
                        "коммерческое предложение",
                        "начальная",
                        "под одной",
                    )
                )
            ):
                pending_name.append(meaningful[0])
            continue
        lowered = " ".join(meaningful).lower()
        if any(
            marker in lowered
            for marker in (
                "наименование услуг",
                "коммерческое предложение",
                "используемый метод",
                "начальная сумма",
                "итого",
                "всего",
                "максимальное значение цены",
                "под одной условной единицей",
            )
        ):
            continue
        unit_index = next(
            (
                i
                for i, value in enumerate(meaningful)
                if re.fullmatch(
                    r"(?:условная\s+единица|нормо[ -]?час(?:а|ов)?)",
                    value,
                    re.IGNORECASE,
                )
            ),
            None,
        )
        if unit_index is None or unit_index == 0:
            continue
        raw_name = " ".join([*pending_name, *meaningful[:unit_index]]).strip()
        pending_name = []
        prices = [_parse_float(value) for value in meaningful[unit_index + 1 :]]
        prices = [value for value in prices if value is not None]
        if not raw_name or not prices:
            continue
        name = _normalize_supply_name(raw_name)
        key = (_normalize_supply_name_key(name), meaningful[unit_index].lower())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        evidence_seed = f"{source_document}|service-table|{row_number}|{name}".encode()
        evidence_id = f"ev-{hashlib.sha256(evidence_seed).hexdigest()[:16]}"
        rows.append(
            supply_item_type(
                item_no=None,
                name=name,
                quantity=None,
                unit=_normalize_supply_unit(meaningful[unit_index]),
                characteristics=[],
                gost=[],
                equivalent_allowed=None,
                source_document=source_document,
                source_kind="nmck_service_table",
                confidence="high",
                raw_fragment=raw_line,
                unit_price=_format_decimal_price(prices[-1]),
                total_price=None,
                source_documents=[source_document],
                item_type="service",
                quantity_status="not_specified",
                pricing_basis="conditional_unit_price"
                if "условн" in meaningful[unit_index].lower()
                else "hourly_rate",
                source_row_number=row_number,
                evidence_id=evidence_id,
                unit_original=meaningful[unit_index],
            )
        )
    return rows


def extract_supply_items_from_notification_xml(
    text: str,
    source_document: str,
    *,
    supply_item_type: type[TItem],
    _normalize_supply_name: Callable[[str | None], str],
    _parse_float: Callable[[str | None], float | None],
    _normalize_quantity_value: Callable[[str | None], str | None],
    _normalize_supply_unit: Callable[[str | None], str | None],
    _extract_gost_tokens: Callable[[str], list[str]],
    _format_decimal_price: Callable[[float | None], str | None],
) -> list[TItem]:
    """Extract purchaseObject rows from the notification XML returned by EIS.

    EIS notification XML is source-backed and contains the canonical item name,
    OKEI, price and quantity.  It is commonly classified as a supporting file,
    so it must be parsed independently of the human-readable attachments.
    """
    if not text or "purchaseObject" not in text:
        return []
    rows: list[TItem] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    objects = [
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "purchaseObject"
    ]
    for row_number, element in enumerate(objects, start=1):

        def direct_child(tag: str) -> ET.Element | None:
            return next(
                (node for node in element if node.tag.rsplit("}", 1)[-1] == tag), None
            )

        def nested_child(parent: ET.Element | None, tag: str) -> ET.Element | None:
            if parent is None:
                return None
            return next(
                (node for node in parent.iter() if node.tag.rsplit("}", 1)[-1] == tag),
                None,
            )

        def descendants(tag: str) -> list[ET.Element]:
            return [
                node for node in element.iter() if node.tag.rsplit("}", 1)[-1] == tag
            ]

        def value(tag: str) -> str:
            node = next(iter(descendants(tag)), None)
            return (
                html.unescape(" ".join(node.itertext()).strip())
                if node is not None
                else ""
            )

        # The direct purchaseObject name is the item.  A descendant search can
        # otherwise select the first KTRU characteristic name as the product.
        ktru = next(iter(descendants("KTRU")), None)
        name_node = direct_child("name")
        if name_node is None:
            name_node = next(
                (
                    node
                    for node in (ktru.iter() if ktru is not None else [])
                    if node.tag.rsplit("}", 1)[-1] == "name"
                ),
                None,
            )
        name = _normalize_supply_name(
            " ".join(name_node.itertext()).strip() if name_node is not None else ""
        )
        characteristics = []
        for characteristic in descendants("characteristicsUsingTextForm"):
            characteristic_name = next(
                (
                    node
                    for node in characteristic
                    if node.tag.rsplit("}", 1)[-1] == "name"
                ),
                None,
            )
            if characteristic_name is not None:
                label = " ".join(characteristic_name.itertext()).strip()
                value_node = next(
                    (
                        node
                        for node in characteristic.iter()
                        if node.tag.rsplit("}", 1)[-1]
                        in {"concreteValue", "min", "max"}
                    ),
                    None,
                )
                unit_node = next(
                    (
                        node
                        for node in characteristic.iter()
                        if node.tag.rsplit("}", 1)[-1] == "nationalCode"
                    ),
                    None,
                )
                if value_node is not None:
                    comparator = (
                        "≥ "
                        if any(
                            node.tag.rsplit("}", 1)[-1] == "minMathNotation"
                            and "greaterOrEqual" in " ".join(node.itertext())
                            for node in characteristic.iter()
                        )
                        else ""
                    )
                    unit_value = (
                        " ".join(unit_node.itertext()).strip()
                        if unit_node is not None
                        else ""
                    )
                    characteristics.append(
                        f"{label} {comparator}{' '.join(value_node.itertext()).strip()} {unit_value}".strip()
                    )
        raw_type = value("type").upper()
        price = _parse_float(value("price"))
        total = _parse_float(value("sum"))
        quantity_node = direct_child("quantity")
        if quantity_node is None:
            drug_customer_info = nested_child(
                direct_child("drugQuantityCustomersInfo"), "drugQuantityCustomerInfo"
            )
            quantity_node = nested_child(drug_customer_info, "quantity")
        quantity_raw = ""
        if quantity_node is not None:
            quantity_value_node = next(
                (
                    node
                    for node in quantity_node.iter()
                    if node.tag.rsplit("}", 1)[-1] in {"value", "concreteValue"}
                ),
                None,
            )
            quantity_raw = (
                " ".join(quantity_value_node.itertext()).strip()
                if quantity_value_node is not None
                else " ".join(quantity_node.itertext()).strip()
            )
        quantity = (
            _normalize_quantity_value(quantity_raw)
            if re.search(r"\d", quantity_raw)
            else None
        )
        okei = direct_child("OKEI")
        if okei is None:
            drug_info = nested_child(element, "drugInfo")
            okei = nested_child(drug_info, "manualUserOKEI")
        unit_node = next(
            (
                node
                for node in (okei.iter() if okei is not None else [])
                if node.tag.rsplit("}", 1)[-1] in {"nationalCode", "name"}
            ),
            None,
        )
        unit = _normalize_supply_unit(
            " ".join(unit_node.itertext()).strip() if unit_node is not None else None
        )
        if not name or price is None and total is None:
            continue
        item_type = "service" if raw_type in {"SERVICE", "WORK"} else "goods"
        evidence_seed = (
            f"{source_document}|notification-xml|{row_number}|{name}".encode()
        )
        rows.append(
            supply_item_type(
                item_no=None,
                name=name,
                quantity=quantity,
                unit=unit,
                characteristics=characteristics,
                gost=_extract_gost_tokens(" ".join(element.itertext())),
                equivalent_allowed=None,
                source_document=source_document,
                source_kind="notification_xml",
                confidence="high",
                raw_fragment=" ".join(element.itertext()).strip(),
                unit_price=_format_decimal_price(price),
                total_price=_format_decimal_price(total),
                source_documents=[source_document],
                item_type=item_type,
                quantity_status="specified"
                if quantity is not None and unit
                else "not_specified",
                pricing_basis="unit_price",
                source_row_number=row_number,
                evidence_id=f"ev-{hashlib.sha256(evidence_seed).hexdigest()[:16]}",
                unit_original=unit,
                name_source_type="structured_direct_name"
                if direct_child("name") is not None
                else "structured_item_title",
                name_source_path="purchaseObject/name"
                if direct_child("name") is not None
                else "purchaseObject/KTRU/name",
                quantity_source_path="purchaseObject/quantity",
                unit_source_path="purchaseObject/OKEI",
                source_record_id=value("sid") or None,
                extraction_strategy="notification_xml_purchase_object",
            )
        )
    return rows
