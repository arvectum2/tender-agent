"""Actual source-style 44-FZ 1C PDF rubric is NOT a generic CZN 70/30 NO_GO."""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from src.modules.company_profile_store.qualification_44_alternate_observer import (
    observe_44_alternate_pdf_text,
    verify_44_alternate_originals,
)

PDF_TEXT = """ПОРЯДОК
Рассмотрения и оценки заявок на участие в конкурсе

1. Цена контракта,       60       - 100
4. Квалификация         40       наличие опыта работы
    контракта           5       характеристика 100
    наличие у           95      характеристика 100

4.4. Показатель оценки - характеристика N 2
   общее количество исполненных Контрактов (договоров)
   перечень специалистов и иных работников, их квалификация
"""


def _zip(files):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return raw.getvalue()


def _fake_original(*, latest_version=2, url_host="zakupki.gov.ru"):
    uid = "01A0F69F0B337A1996519D98C9AA2046"
    doc = b"%PDF-standin-for-test-no-real-artifact"
    deadline = "2026-10-22T08:00:00+03:00"
    doc_name = "Приложение 5 Порядок оценки Зюзино 1С .pdf"
    url = (
        "https://" + url_host +
        "/44fz/filestore/public/1.0/download/priz/file.html?uid=" + uid
    )
    def version_xml(version):
        return (
            "<root><epNotificationEOK2020>"
            "<purchaseNumber>0173300009226000009</purchaseNumber>"
            f"<versionNumber>{version}</versionNumber>"
            f"<endDT>{deadline}</endDT>"
            "<attachmentInfo>"
            f"<publishedContentId>{uid}</publishedContentId>"
            f"<fileName>{doc_name}</fileName>"
            f"<fileSize>{len(doc)}</fileSize>"
            f"<url>{url}</url>"
            "</attachmentInfo></epNotificationEOK2020></root>"
        ).encode()
    latest = version_xml(latest_version)
    file_map = {
        f"notice_{v}.xml": latest if v == latest_version else version_xml(v)
        for v in sorted({1, latest_version})
    }
    soap = _zip(file_map)
    receipt = {
        "procurement_number": "0173300009226000009",
        "procurement_law": "44fz",
        "procurement_notice_version": 2,
        "original_soap_archive_sha256": hashlib.sha256(soap).hexdigest(),
        "original_notice_xml_sha256": hashlib.sha256(latest).hexdigest(),
        "scoring_document_uid": uid,
        "scoring_document_sha256": hashlib.sha256(doc).hexdigest(),
        "scoring_document_size_bytes": len(doc),
        "scoring_document_name": doc_name,
        "original_application_deadline": deadline,
    }
    return soap, doc, receipt


def test_second_real_style_44_fz_composite_scoring_requires_specialist_review():
    data = observe_44_alternate_pdf_text(PDF_TEXT)
    assert data["price_weight_percent"] == 60
    assert data["qualification_weight_percent"] == 40
    assert data["qualification_subweights_percent"] == {
        "completed_contract_count": 5,
        "specialists": 95,
    }
    assert data["completed_contracts_full_score_percent"] is None
    assert data["owner_contract_reference_count_used"] is False
    assert data["commercial_recommendation"] == "NOT_ASSESSED"
    assert data["human_gold"] is False
    assert data["external_action_allowed"] is False


@pytest.mark.parametrize("before,after", [
    ("Цена контракта,       60", "Цена контракта,       70"),
    ("Квалификация         40", "Квалификация         60"),
    ("контракта           5", "контракта           50"),
    ("наличие у           95", "наличие у           90"),
    ("количество исполненных Контрактов", "наличие полного бизнеса"),
    ("перечень специалистов и иных работников", "наша экспертиза"),
    ("ПОРЯДОК", "ДРУГОЙ ДОКУМЕНТ"),
])
def test_alternate_44_rubric_abstains_on_ambiguous_or_changed_criteria(before, after):
    with pytest.raises(ValueError):
        observe_44_alternate_pdf_text(PDF_TEXT.replace(before, after))


def test_duplicate_price_row_rejected():
    with pytest.raises(ValueError, match="ambiguous"):
        observe_44_alternate_pdf_text(PDF_TEXT + "\n1. Цена контракта, 60 - 100")


def test_original_alternate_notice_pdf_version_uid_sha_and_deadline_verify():
    soap, doc, receipt = _fake_original()
    src = verify_44_alternate_originals(
        soap_archive_bytes=soap, scoring_pdf_bytes=doc, receipt=receipt,
    )
    assert src["procurement_number"] == "0173300009226000009"
    assert src["notice_version"] == 2
    assert src["application_deadline"] == "2026-10-22T08:00:00+03:00"
    assert src["digital_signature_validated"] is False


@pytest.mark.parametrize("mutation", [
    "soap", "doc", "uid", "host", "expired_notice", "deadline", "name", "size",
])
def test_alternate_source_mutation_fails_closed(mutation):
    soap, doc, receipt = _fake_original(
        latest_version=1 if mutation == "expired_notice" else 2,
        url_host="attacker.invalid" if mutation == "host" else "zakupki.gov.ru",
    )
    if mutation == "soap":
        soap += b"changed"
    elif mutation == "doc":
        doc += b"changed"
    elif mutation == "uid":
        receipt["scoring_document_uid"] = "A" * 32
    elif mutation == "deadline":
        receipt["original_application_deadline"] = "2026-10-23T08:00:00+03:00"
    elif mutation == "name":
        receipt["scoring_document_name"] = "other.pdf"
    elif mutation == "size":
        receipt["scoring_document_size_bytes"] = 1
    with pytest.raises(ValueError):
        verify_44_alternate_originals(
            soap_archive_bytes=soap, scoring_pdf_bytes=doc, receipt=receipt,
        )
