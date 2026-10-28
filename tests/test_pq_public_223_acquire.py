import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.modules.market_intelligence.pq_public_223_acquire import (
    _source_documents_url,
    acquire,
    batch,
)

NUMBER = "32615969197"
GUID = "a10525c4-dab9-42ff-b596-d1bc02709519"
CARD = ("https://zakupki.gov.ru/epz/order/notice/notice223/signview/listModal.html"
        f"?purchaseNoticeGuid={GUID}&purchaseNoticeNumber={NUMBER}")
FILE_URL = ("https://zakupki.gov.ru/223/filestore/public/1.0/"
            "download/fz223/file.html?uid=" + "a" * 32)


def _provider(html_number: str = NUMBER):
    card = SimpleNamespace(registry_number=NUMBER, card_url=CARD)
    link = SimpleNamespace(file_name="evidence.pdf", url=FILE_URL)
    return SimpleNamespace(
        search=Mock(return_value=SimpleNamespace(status="success", items=[card])),
        fetch_detail=Mock(return_value=SimpleNamespace(
            network_status="success", common_info_html=html_number,
            document_links=[link],
        )),
    )


def _downloader():
    result = Mock()
    def download(attachments, **kw):
        destination = kw["target_dir"]
        destination.mkdir(parents=True, exist_ok=True)
        data = b"%PDF-1.5\noriginal evidence"
        (destination / "evidence.pdf").write_bytes(data)
        result.saved = [SimpleNamespace(
            stored_name="evidence.pdf", name="evidence.pdf",
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data), source_url=attachments[0].url)]
        result.skipped = []
        return result
    return Mock(side_effect=download)


def test_exact_source_card_guid_only():
    assert NUMBER in _source_documents_url(CARD, NUMBER)
    assert _source_documents_url(CARD.replace("zakupki.gov.ru", "evil.example"), NUMBER) is None
    assert _source_documents_url(CARD.replace(NUMBER, "32615614821"), NUMBER) is None
    assert _source_documents_url(CARD.replace(GUID, "not-guid"), NUMBER) is None


def test_download_source_page_receipt_redacts_uid_and_is_idempotent(tmp_path: Path):
    provider = _provider()
    download = _downloader()
    result = acquire(registry_number=NUMBER, target_root=tmp_path,
                     provider=provider, download=download)
    assert result["files_saved"] == 1
    assert download.call_count == 1
    receipt = tmp_path / NUMBER / "public-page-receipt.json"
    text = receipt.read_text()
    assert FILE_URL not in text
    assert ("a" * 32) not in text
    evidence = json.loads(text)
    assert evidence["revision_review_required"] is True
    assert evidence["signed_contract_verified"] is False
    assert evidence["source_level"] == "verified_public_page_not_original_soap_xml"
    again = acquire(registry_number=NUMBER, target_root=tmp_path,
                    provider=provider, download=download)
    assert again["status"] == "existing_receipt"
    assert download.call_count == 1


def test_refuse_mismatched_official_html(tmp_path: Path):
    provider = _provider("irrelevant notice only")
    download = _downloader()
    result = acquire(registry_number=NUMBER, target_root=tmp_path,
                     provider=provider, download=download)
    assert result["status"] == "documents_page_unavailable_or_mismatch"
    assert download.call_count == 0


def test_batch_journal_does_not_redownload(tmp_path: Path):
    gaps = tmp_path / "gaps.json"
    gaps.write_text(json.dumps({"cases": [{"procedure_id": NUMBER}]}))
    journal = tmp_path / "attempts.json"
    roots = tmp_path / "originals"
    downloader = _downloader()
    result = batch(gaps=gaps, target_root=roots, journal=journal,
                   provider=_provider(), download=downloader)
    assert result["downloaded_count"] == 1
    again = batch(gaps=gaps, target_root=roots, journal=journal,
                  provider=_provider(), download=downloader)
    assert again["cases_attempted"] == 0
    assert downloader.call_count == 1


def test_final_protocol_precedes_other_attachments(tmp_path: Path):
    provider = _provider()
    other = SimpleNamespace(file_name="Итоговый протокол.pdf",
                            url=FILE_URL.replace("a" * 32, "b" * 32))
    detail = provider.fetch_detail.return_value
    detail.document_links.append(other)
    downloader = _downloader()
    result = acquire(registry_number=NUMBER, target_root=tmp_path,
                     provider=provider, max_files=1, download=downloader)
    assert result["files_saved"] == 1
    forwarded = downloader.call_args.args[0]
    assert forwarded[0].name == "Итоговый протокол.pdf"
    receipt = json.loads((tmp_path / NUMBER / "public-page-receipt.json").read_text())
    assert receipt["source_links_discovered"] == 2
    assert receipt["source_links_selected"] == 1
    assert receipt["coverage_incomplete"] is True

def test_original_public_223_7z_receipt_is_opaque_and_source_bound(tmp_path: Path):
    from src.modules.tender_operator_agent_demo.attachment_downloader import (
        download_procurement_attachments,
    )

    provider = _provider()
    provider.fetch_detail.return_value.document_links = [
        SimpleNamespace(file_name="protocol.7z", url=FILE_URL)
    ]
    opaque = b"7z\xbc\xaf\x27\x1c" + b"opaque-eis-223-archive"

    def download(attachments, **kwargs):
        kwargs["transport"] = lambda *_args: (opaque, "application/x-7z-compressed")
        return download_procurement_attachments(attachments, **kwargs)

    outcome = acquire(registry_number=NUMBER, target_root=tmp_path,
                      provider=provider, download=download)
    assert outcome["files_saved"] == 1
    receipt = json.loads((tmp_path / NUMBER / "public-page-receipt.json").read_text())
    assert receipt["source_level"] == "verified_public_page_not_original_soap_xml"
    assert receipt["signed_contract_verified"] is False
    assert receipt["revision_review_required"] is True
    assert receipt["files"][0]["sha256"] == hashlib.sha256(opaque).hexdigest()
    assert receipt["files"][0]["original_name"] == "protocol.7z"
    assert (tmp_path / NUMBER / receipt["files"][0]["filename"]).read_bytes() == opaque
