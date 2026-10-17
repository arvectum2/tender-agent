"""No model reads blind source files: XLSX tests only use synthetic workbooks."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest
from openpyxl import Workbook

from src.modules.benchmark_pipeline.contract import BenchmarkContractError
from src.modules.tender_operator_agent_demo.r4_external_gold_intake import (
    _quotes_exactly_grounded,
)
from src.modules.tender_operator_agent_demo.r4_original_text_extract import (
    verified_document_text,
)

QUOTE = "Исполнитель обязан предоставить исключительные права на результат."


def workbook_bytes(*, formula: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Спецификация"
    sheet["B2"] = QUOTE
    sheet["C4"] = "Срок исполнения"
    sheet["D6"] = QUOTE
    if formula:
        sheet["A1"] = "=CONCATENATE(B2,C4)"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def quote_gate(tmp_path: Path, raw: bytes, *, locator: str, quote: str) -> None:
    path = tmp_path / "primary.xlsx"
    path.write_bytes(raw)
    document = {
        "path": "primary.xlsx",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source_url": "https://example.test/original",
    }
    bundle = {"documents": [document]}
    discovery = {
        "label": "RELEVANT",
        "evidence": [{"source_ref": "primary.xlsx", "quote": quote, "locator": locator}],
    }
    truth = {"facts": []}
    _quotes_exactly_grounded(bundle, discovery, truth, tmp_path)


def test_static_xlsx_cell_quote_is_exact_and_locator_checked(tmp_path):
    source = workbook_bytes()
    text = verified_document_text(source, "primary.xlsx")
    assert "SHEET-Спецификация CELL-B2: " + QUOTE in text
    quote_gate(tmp_path, source, locator="SHEET-Спецификация CELL-B2", quote=QUOTE)
    with pytest.raises(BenchmarkContractError, match="claimed source"):
        quote_gate(tmp_path, source, locator="SHEET-Спецификация CELL-C4", quote=QUOTE)
    with pytest.raises(BenchmarkContractError, match="exact sheet"):
        quote_gate(tmp_path, source, locator="UNKNOWN", quote=QUOTE)
    with pytest.raises(BenchmarkContractError, match="claimed source"):
        quote_gate(
            tmp_path, source, locator="SHEET-Спецификация CELL-B2",
            quote="SHEET-Спецификация CELL-B2",
        )
    with pytest.raises(BenchmarkContractError, match="verbatim"):
        quote_gate(
            tmp_path, source, locator="SHEET-Спецификация CELL-B2",
            quote="Поставщик обязан заменить всё оборудование в течение года.",
        )


def test_formulas_are_not_silently_accepted_as_source_text(tmp_path):
    raw = workbook_bytes(formula=True)
    with pytest.raises(ValueError, match="Formula"):
        verified_document_text(raw, "primary.xlsx")
    with pytest.raises(BenchmarkContractError, match="unsearchable"):
        quote_gate(tmp_path, raw, locator="SHEET-Спецификация CELL-B2", quote=QUOTE)


def test_original_zip_with_single_static_xlsx_supported_only(tmp_path):
    data = workbook_bytes()
    archive = BytesIO()
    with ZipFile(archive, "w") as z:
        z.writestr("specification.xlsx", data)
    text = verified_document_text(archive.getvalue(), "official-original.zip")
    assert f"SHEET-Спецификация CELL-B2: {QUOTE}" in text


def test_non_workbook_binary_and_empty_xlsx_fail_closed():
    with pytest.raises(BadZipFile):
        verified_document_text(b"not-a-workbook", "attached.xlsx")
    workbook = Workbook()
    payload = BytesIO()
    workbook.save(payload)
    with pytest.raises(ValueError, match="No literal"):
        verified_document_text(payload.getvalue(), "empty.xlsx")


def test_no_macro_extension_or_unsupported_formats():
    with pytest.raises(ValueError, match="Unsupported"):
        verified_document_text(b"pretend spreadsheet", "macros.xlsm")
