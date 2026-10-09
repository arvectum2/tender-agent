"""Source-verified operator facts from the original, registry-matched EIS notice XML.

APR-03B: do not equate a generic source label with an attributable citation.
Only actual values read from the preserved notice file may become KNOWN.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_input_dir,
    load_demo_run_metadata,
)

_FIELDS = {
    "procurement_title": ("purchaseObjectInfo", "Предмет закупки"),
    "application_deadline": ("endDT", "Окончание подачи заявок"),
    "nmck": ("maxPrice", "НМЦК"),
}
_MAX_XML_BYTES = 5 * 1024 * 1024
_NUMBER = re.compile(r"\d{19}\Z")


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _values(root: ET.Element, tag: str) -> list[str]:
    return list(dict.fromkeys(
        (element.text or "").strip()
        for element in root.iter()
        if _tag(element) == tag and (element.text or "").strip()
    ))


def _unknown() -> dict[str, Any]:
    return {"status": "UNKNOWN", "value": None, "evidence": []}


def _notice_xml(run_id: str, metadata: dict[str, Any]) -> tuple[ET.Element, dict[str, Any]] | None:
    # All paths are obtained from the existing run directory; never from an HTTP parameter.
    directory = get_demo_run_input_dir(run_id).resolve()
    matches: list[tuple[ET.Element, dict[str, Any]]] = []
    for item in metadata.get("files") or []:
        if not isinstance(item, dict) or str(item.get("extension") or "").lower() != ".xml":
            continue
        stored = str(item.get("stored_name") or "")
        if not stored:
            continue
        path = (directory / stored).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            continue
        if path.stat().st_size > _MAX_XML_BYTES:
            continue
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            continue
        try:
            parsed = ET.fromstring(raw)
        except ET.ParseError:
            continue
        matches.append((parsed, item))
    number = str(
        metadata.get("procurement_notice_number")
        or metadata.get("procurement_id")
        or ""
    ).strip()
    if not _NUMBER.fullmatch(number):
        return None
    valid = [
        (xml, item) for xml, item in matches
        if [n for n in _values(xml, "purchaseNumber") if _NUMBER.fullmatch(n)] == [number]
    ]
    # Multiple matching notice revisions need explicit revision selection elsewhere.
    return valid[0] if len(valid) == 1 else None


def _verified_fact(root: ET.Element, item: dict[str, Any], key: str) -> dict[str, Any]:
    tag, _label = _FIELDS[key]
    values = _values(root, tag)
    if len(values) != 1:
        return _unknown()
    excerpt = values[0]
    if key == "nmck":
        try:
            price = Decimal(excerpt)
        except InvalidOperation:
            return _unknown()
        if not price.is_finite() or price < 0:
            return _unknown()
        value: str | float = float(price)
    else:
        value = excerpt
    filename = Path(str(item.get("display_name") or item.get("original_name") or "")).name
    file_id = str(item.get("file_id") or "").strip()
    if not filename or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", file_id):
        return _unknown()
    return {
        "status": "KNOWN",
        "value": value,
        "evidence": [{
            "source_ref": "eis-xml:" + file_id + ":" + tag,
            "document": filename,
            "locator": "XML:" + tag,
            "excerpt": excerpt,
            "file_id": file_id,
        }],
    }


def get_operator_source_evidence(run_id: str) -> dict[str, Any]:
    metadata = load_demo_run_metadata(run_id)
    # The operator source layer is never permitted to present demo/manual files
    # as official EIS evidence, or to silently promote 223-FZ as supported.
    source = str(metadata.get("procurement_source") or "")
    regime = str(metadata.get("procurement_law") or "").lower()
    facts = {field: _unknown() for field in _FIELDS}
    warnings: list[str] = []
    if source != "zakupki_gov_ru_getdocs_ip" or "44" not in regime:
        warnings.append("Нет подтверждённого исходного извещения XML ЕИС 44-ФЗ для этого запуска.")
    else:
        matched = _notice_xml(run_id, metadata)
        if not matched:
            warnings.append("XML не найден или реестровый номер/редакция извещения не подтверждены.")
        else:
            xml, item = matched
            for field in facts:
                facts[field] = _verified_fact(xml, item, field)
            if any(value["status"] != "KNOWN" for value in facts.values()):
                warnings.append("Часть полей XML неоднозначна или отсутствует; требуется проверка.")

    # Do not use the old report's claimed status to prove the content of EIS XML.
    return {
        "contract_version": "operator-eis-source-evidence-v1",
        "run_id": run_id,
        "registry_number": metadata.get("procurement_notice_number") or metadata.get("procurement_id"),
        "source": source,
        "facts": facts,
        "warnings": warnings,
        "human_control_required": True,
        "external_action_allowed": False,
    }
