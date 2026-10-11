"""Offline, no-network public EIS receipt and trust-boundary checks."""

from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.eis_public_original_receipts import (
    _fetch,
    fetch_public_original_receipts,
    parse_public_document_links,
    public_documents_url,
)

NUMBER = "0372200172326000015"
UID = "01A10C59B0B8791B8D464C4C14D10A94"
URL = public_documents_url(NUMBER, "zk20")
FILE_URL = f"https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={UID}"


def _page(href=FILE_URL):
    return (
        f"<html><body><header>№ {NUMBER}</header>"
        "<div>Редакция <span>Действующая</span></div>"
        "<div>Размещено <time>08.10.2026</time></div>"
        f'<a href="{href}">Описание объекта закупки</a></body></html>'
    ).encode()


def test_public_link_parser_preserves_registry_page_labels_and_uid():
    sources, manifest = parse_public_document_links(
        _page(), page_url=URL, reg_number=NUMBER
    )
    assert len(sources) == 1
    assert sources[0].uid == UID
    assert sources[0].title == "Описание объекта закупки"
    assert manifest["page_sha256"] == hashlib.sha256(_page()).hexdigest()
    assert manifest["page_edition_ui_label"] == "Действующая"
    assert manifest["page_posted_ui_date"] == "08.10.2026"
    assert manifest["independent_eis_revision_verified"] is False
    assert manifest["data_platform_identity_verified"] is False


@pytest.mark.parametrize(
    ("page", "url", "number", "code"),
    [
        (_page(), URL, "0000000000000000000", "NOTICE_NUMBER_MISMATCH"),
        (
            _page(FILE_URL.replace("zakupki.gov.ru", "attacker.example")),
            URL,
            NUMBER,
            "UNTRUSTED_EIS_URL",
        ),
        (_page(FILE_URL.replace(UID, "BAD")), URL, NUMBER, "UNTRUSTED_FILE_UID"),
        (
            _page(FILE_URL).replace(
                b"</body>", f'<a href="{FILE_URL}">duplicate</a></body>'.encode()
            ),
            URL,
            NUMBER,
            "DUPLICATE_FILE_UID",
        ),
        (f"<body>{NUMBER}</body>".encode(), URL, NUMBER, "NO_OFFICIAL_DOCUMENT_LINKS"),
        (b"<body>Wrong notice</body>", URL, NUMBER, "NOTICE_NUMBER_NOT_ON_PAGE"),
    ],
)
def test_public_pages_fail_closed(page, url, number, code):
    with pytest.raises(ValueError, match=code):
        parse_public_document_links(page, page_url=url, reg_number=number)


@pytest.mark.parametrize(
    ("number", "type_"),
    [("../etc/passwd", "zk20"), (NUMBER, "../zk20"), ("42", "zk20")],
)
def test_invalid_registry_and_notice_types_rejected(number, type_):
    with pytest.raises(ValueError, match="INVALID_PROCUREMENT_REQUEST"):
        public_documents_url(number, type_)


class FakeResponse:
    def __init__(self, value, url):
        self.value, self.url = value, url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self):
        return self.url

    def read(self, size):
        return self.value[:size]


class FakeOpener:
    def __init__(self, page, binary):
        self.payloads = {URL: page, FILE_URL: binary}

    def open(self, request, timeout):
        return FakeResponse(self.payloads[request.full_url], request.full_url)


def test_public_fetch_uses_source_bytes_not_fabricated_dp_identity():
    original = b"%PDF-1.5\\nsource bytes\\n"
    manifest, sources = fetch_public_original_receipts(
        reg_number=NUMBER, notice_type="zk20", opener=FakeOpener(_page(), original)
    )
    assert sources == {UID: original}
    assert manifest["total_bytes"] == len(original)
    assert manifest["files"][0]["sha256"] == hashlib.sha256(original).hexdigest()
    assert manifest["files"][0]["persisted_dp_resource_id"] is None
    assert manifest["files"][0]["persisted_dp_document_id"] is None


def test_filestore_html_is_not_accepted_as_original_binary():
    with pytest.raises(ValueError, match="FILESTORE_RETURNED_HTML"):
        _fetch(
            FILE_URL,
            attachment=True,
            max_size=1000,
            opener=FakeOpener(_page(), b"<html>error</html>"),
        )


def test_attachment_budget_fails_closed():
    with pytest.raises(ValueError, match="INVALID_OR_OVERSIZED_CONTENT"):
        _fetch(
            FILE_URL,
            attachment=True,
            max_size=10,
            opener=FakeOpener(_page(), b"x" * 30),
        )


def test_cross_host_redirect_rejected_before_request():
    from urllib.request import Request

    from src.modules.tender_operator_agent_demo.eis_public_original_receipts import (
        _SafeRedirects,
    )

    redirector = _SafeRedirects()
    with pytest.raises(ValueError, match="UNTRUSTED_EIS_URL"):
        redirector.redirect_request(
            Request(FILE_URL), None, 302, "Found", {}, "https://evil.example/payload"
        )


def test_originals_cli_writes_parseable_manifest_only_into_new_directory(
    monkeypatch, tmp_path
):
    import json
    import sys

    from scripts.ops import audit_public_eis_originals

    original = b"%PDF-1.5 original"
    monkeypatch.setattr(
        audit_public_eis_originals,
        "fetch_public_original_receipts",
        lambda **kwargs: (
            {
                "procurement_number": NUMBER,
                "total_bytes": len(original),
                "page_edition_ui_label": "Действующая",
                "independent_eis_revision_verified": False,
                "data_platform_identity_verified": False,
                "files": [{"uid": UID, "sha256": hashlib.sha256(original).hexdigest()}],
            },
            {UID: original},
        ),
    )
    output = tmp_path / "never-existed"
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_public_eis_originals.py", NUMBER, "zk20", "--output", str(output)],
    )
    assert audit_public_eis_originals.main() == 0
    assert json.loads((output / "receipts.json").read_text())["total_bytes"] == len(
        original
    )
    assert (output / f"{UID}.bin").read_bytes() == original
    with pytest.raises(FileExistsError):
        audit_public_eis_originals.main()
