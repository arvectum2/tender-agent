"""Read-only real-EIS replay harness: test protocol, never a production run."""
from __future__ import annotations

import hashlib
import io
import json
import types
import zipfile
from datetime import date

import pytest

from scripts.acceptance.replay_original_44_owned_run import (
    replay_original_owned_run,
)
from src.modules.company_profile_store import qualification_run_composite_pdf

PDF_TEXT = """ПОРЯДОК
Рассмотрения и оценки заявок на участие в конкурсе
1. Цена контракта, 60 100
4. Квалификация 40 100
    контракта 5 характеристика
    наличие у 95 характеристика
количество исполненных Контрактов (договоров)
перечень специалистов и иных работников
"""


def _offline_original_fixture(tmp_path):
    registry = "0173300009226000009"
    uid = "01A0F69F0B337A1996519D98C9AA2046"
    pdf = b"%PDF-1.7\nsynthetic-unit-test-pdf-not-real-document\n"
    doc_name = "Приложение 5 Порядок оценки Зюзино 1С .pdf"
    url = (
        "https://zakupki.gov.ru/44fz/filestore/public/1.0/"
        f"download/priz/file.html?uid={uid}"
    )
    xml = (
        "<root><epNotificationEOK2020>"
        f"<purchaseNumber>{registry}</purchaseNumber>"
        "<versionNumber>2</versionNumber>"
        "<endDT>2026-10-22T08:00:00+03:00</endDT>"
        "<attachmentInfo>"
        f"<publishedContentId>{uid}</publishedContentId>"
        f"<fileName>{doc_name}</fileName>"
        f"<fileSize>{len(pdf)}</fileSize>"
        f"<url>{url}</url>"
        "</attachmentInfo></epNotificationEOK2020></root>"
    ).encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as container:
        container.writestr(
            f"epNotificationEOK2020_{registry}_2_00000000000000000000000000000000.xml",
            xml,
        )
    zip_path = tmp_path / "original-eis.zip"
    pdf_path = tmp_path / "evaluation.pdf"
    receipt_path = tmp_path / "receipt.json"
    zip_path.write_bytes(archive.getvalue())
    pdf_path.write_bytes(pdf)
    receipt_path.write_text(json.dumps({
        "schema_version": "eis-original-composite-scoring-receipt-v1",
        "procurement_law": "44fz",
        "procurement_number": registry,
        "procurement_notice_version": 2,
        "original_soap_archive_sha256": hashlib.sha256(archive.getvalue()).hexdigest(),
        "original_notice_xml_sha256": hashlib.sha256(xml).hexdigest(),
        "scoring_document_uid": uid,
        "scoring_document_sha256": hashlib.sha256(pdf).hexdigest(),
        "scoring_document_name": doc_name,
        "scoring_document_size_bytes": len(pdf),
        "original_application_deadline": "2026-10-22T08:00:00+03:00",
    }), encoding="utf-8")
    return zip_path, pdf_path, receipt_path


def test_temporary_replay_is_source_bound_and_rejects_modified_copy(
    tmp_path, monkeypatch,
):
    soap, pdf, receipt = _offline_original_fixture(tmp_path)
    soap_before, pdf_before = soap.read_bytes(), pdf.read_bytes()
    monkeypatch.setattr(
        qualification_run_composite_pdf.subprocess, "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            stdout=PDF_TEXT.encode("utf-8"),
        ),
    )
    result = replay_original_owned_run(
        soap_archive=soap, evaluation_pdf=pdf,
        receipt_path=receipt, as_of=date(2026, 10, 13),
    )
    assert result["competitive_recommendation"] == "NOT_ASSESSED"
    assert result["qualification_subweights_percent"] == {
        "completed_contract_count": 5,
        "specialists": 95,
    }
    assert result["tampered_copy_source_status"] == (
        "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
    )
    assert result["tenant_database_accessed"] is False
    assert result["production_saas_login_tested"] is False
    assert soap.read_bytes() == soap_before
    assert pdf.read_bytes() == pdf_before


@pytest.mark.parametrize("mutation", ["archive_bytes", "pdf_bytes", "receipt_law"])
def test_original_replay_rejects_unpinned_inputs_before_report(
    tmp_path, mutation,
):
    soap, pdf, receipt = _offline_original_fixture(tmp_path)
    if mutation == "archive_bytes":
        soap.write_bytes(soap.read_bytes() + b"modified")
    elif mutation == "pdf_bytes":
        pdf.write_bytes(pdf.read_bytes() + b"modified")
    else:
        data = json.loads(receipt.read_text())
        data["procurement_law"] = "223fz"
        receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        replay_original_owned_run(
            soap_archive=soap, evaluation_pdf=pdf,
            receipt_path=receipt, as_of=date(2026, 10, 13),
        )
