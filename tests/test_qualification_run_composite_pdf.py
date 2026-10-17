"""Original tenant-run 44-FZ composite PDF fallback never invents competitive NO_GO."""
from __future__ import annotations

import hashlib
import io
import types
import zipfile
from datetime import date

import pytest

from src.modules.company_profile_store import (
    qualification_run_composite_pdf as pdf_run,
)
from src.modules.company_profile_store import (
    qualification_run_service as run_service,
)

FAKE_PDF_TEXT = """ПОРЯДОК
Рассмотрения и оценки заявок на участие в конкурсе
1. Цена контракта,   60       100
4. Квалификация     40       наличие опыта работы
    контракта         5       характеристика
    наличие у         95      характеристика
количество исполненных Контрактов (договоров)
перечень специалистов и иных работников
"""


def _trusted_pdf_run(tmp_path, monkeypatch):
    source = tmp_path / "eis-files"
    source.mkdir()
    run_id = "toa-run-20261013000000-bcda12"
    number = "0173300009226000009"
    uid = "01A0F69F0B337A1996519D98C9AA2046"
    doc_name = "Приложение 5 Порядок оценки Зюзино 1С .pdf"
    url = (
        "https://zakupki.gov.ru/44fz/filestore/public/1.0/"
        f"download/priz/file.html?uid={uid}"
    )
    pdf = b"%PDF-1.7\nsynthetic-fixture-not-a-real-legal-PDF\n"
    (source / "evaluation.pdf").write_bytes(pdf)
    xml = (
        "<root><epNotificationEOK2020>"
        f"<purchaseNumber>{number}</purchaseNumber>"
        "<versionNumber>2</versionNumber>"
        "<endDT>2026-10-22T08:00:00+03:00</endDT>"
        "<attachmentInfo>"
        f"<publishedContentId>{uid}</publishedContentId>"
        f"<fileName>{doc_name}</fileName>"
        f"<fileSize>{len(pdf)}</fileSize>"
        f"<url>{url}</url>"
        "</attachmentInfo></epNotificationEOK2020></root>"
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr(f"epNotificationEOK2020_{number}_2.xml", xml)
    soap = output.getvalue()
    (source / "eis-getdocs.zip").write_bytes(soap)
    meta = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": number,
        "archive_downloaded": True,
        "getdocs_status": "completed",
        "subsystem_type": "PRIZ",
        "token_owner": "individual",
        "archive_source_host": "int.zakupki.gov.ru",
        "archive_stored_name": "eis-getdocs.zip",
        "original_getdocs_archive_sha256": hashlib.sha256(soap).hexdigest(),
        "files": [{
            "source_type": "notice_xml_attachments",
            "stored_name": "evaluation.pdf",
            "original_name": doc_name,
            "source_download_sha256": hashlib.sha256(pdf).hexdigest(),
            "source_url": url,
        }],
    }
    monkeypatch.setattr(run_service, "load_demo_run_metadata", lambda _: meta)
    monkeypatch.setattr(run_service, "get_demo_run_input_dir", lambda _: source)
    monkeypatch.setattr(
        pdf_run.subprocess, "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            stdout=FAKE_PDF_TEXT.encode("utf-8"),
        ),
    )
    return run_id, meta, source


def test_composite_pdf_auto_attaches_source_observation_without_zero_reference_nogo(
    tmp_path, monkeypatch,
):
    run_id, _, _ = _trusted_pdf_run(tmp_path, monkeypatch)
    report = run_service.assess_owned_run_qualification(
        None, run_id=run_id, customer_id="tenant-verified-only",
        as_of=date(2026, 10, 13),
    )
    assert report["competitive_recommendation"] == "NOT_ASSESSED"
    assert report["source_status"] == "ORIGINAL_EIS_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED"
    assert report["qualifying_contracts"] is None
    source = report["criterion_source"]
    assert source["price_weight_percent"] == 60
    assert source["qualification_weight_percent"] == 40
    assert source["qualification_subweights_percent"] == {
        "completed_contract_count": 5, "specialists": 95,
    }
    assert source["observation_as_of"] == "2026-10-13"
    assert source["commercial_recommendation"] == "NOT_ASSESSED"
    assert report["external_action_allowed"] is False
    assert report["human_gold"] is False


@pytest.mark.parametrize("mutation", [
    "old_run", "pdf_changed", "no_document_digest",
    "wrong_law", "wrong_host", "multiple_method_docs",
])
def test_composite_pdf_run_refuses_old_ambiguous_untrusted_or_mutated_sources(
    tmp_path, monkeypatch, mutation,
):
    run_id, metadata, folder = _trusted_pdf_run(tmp_path, monkeypatch)
    if mutation == "old_run":
        metadata.pop("original_getdocs_archive_sha256")
    elif mutation == "pdf_changed":
        p = folder / "evaluation.pdf"
        original = p.read_bytes()
        p.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    elif mutation == "no_document_digest":
        metadata["files"][0].pop("source_download_sha256")
    elif mutation == "wrong_law":
        metadata["subsystem_type"] = "RI223"
    elif mutation == "wrong_host":
        metadata["files"][0]["source_url"] = (
            metadata["files"][0]["source_url"].replace(
                "zakupki.gov.ru", "attacker.invalid"
            )
        )
    elif mutation == "multiple_method_docs":
        metadata["files"].append(dict(metadata["files"][0]))
    result = run_service.assess_owned_run_qualification(
        None, run_id=run_id, customer_id="tenant-verified-only",
        as_of=date(2026, 10, 13),
    )
    assert result["competitive_recommendation"] == "NOT_ASSESSED"
    assert result["source_status"] == "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
    assert "criterion_source" not in result
    assert result["external_action_allowed"] is False


def test_docx_integrity_failure_must_not_route_to_composite_pdf(
    monkeypatch,
):
    monkeypatch.setattr(
        run_service, "discover_run_criterion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("Original scoring DOCX changed after EIS download")
        ),
    )
    monkeypatch.setattr(
        pdf_run, "discover_run_composite_pdf_observation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Tampered DOCX must not attempt composite PDF fallback")
        ),
    )
    result = run_service.assess_owned_run_qualification(
        None, run_id="toa-run-20261013000000-bcda12",
        customer_id="any-tenant", as_of=date(2026, 10, 13),
    )
    assert result["competitive_recommendation"] == "NOT_ASSESSED"
    assert result["source_status"] == "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
