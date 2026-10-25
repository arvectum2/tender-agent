"""The official filestore may fail even when its SOAP notice XML is available."""
from __future__ import annotations

from urllib.error import HTTPError

import pytest

from src.modules.tender_operator_agent_demo import attachment_downloader
from src.modules.tender_operator_agent_demo.attachment_downloader import (
    AttachmentTransportError,
    download_procurement_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementAttachment,
)


@pytest.mark.parametrize("http_code", [404, 429])
def test_official_filestore_rejection_is_explicit_and_does_not_retry(monkeypatch, http_code):
    url = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=01A10C59B0B8791B8D464C4C14D10A94"
    attempts = []

    class RejectedOpener:
        def open(self, request, timeout):
            attempts.append((request.full_url, timeout))
            raise HTTPError(request.full_url, http_code, "Unavailable", {}, None)

    monkeypatch.setattr(
        attachment_downloader,
        "create_urllib_opener",
        lambda target_url, *, follow_redirects, source_direct_connection: RejectedOpener(),
    )
    with pytest.raises(AttachmentTransportError) as caught:
        attachment_downloader._default_transport(url, 1_000_000)
    assert caught.value.code == f"http_status:{http_code}"
    assert attempts == [(url, 30)]


@pytest.mark.parametrize("http_code", [404, 429])
def test_filestore_failure_never_creates_fake_original(monkeypatch, tmp_path, http_code):
    url = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=01A10C59B0B8791B8D464C4C14D10A94"

    def failure(_url, _limit):
        raise AttachmentTransportError(f"http_status:{http_code}")

    attachment = ProcurementAttachment(
        attachment_id="official-attachment", name="original.docx",
        url=url, extension=".docx", can_download=True,
    )
    result = download_procurement_attachments(
        [attachment], target_dir=tmp_path, max_attachments=1,
        max_file_size_bytes=1_000_000, max_total_size_bytes=1_000_000,
        transport=failure,
    )
    assert result.saved == []
    assert len(result.skipped) == 1
    assert result.skipped[0].status == "skipped"
    assert result.skipped[0].stored_name is None
    assert result.skipped[0].error == f"http_status:{http_code}"
    assert list(tmp_path.iterdir()) == []
