"""Bounded read-only public EIS attachment receipts, not notice authenticity proof.

No SOAP token, TLS bypass, or production writes. A public document-page label
is not independent current-notice/revision verification. Filestore files are
public originals whose SHA256 can be compared later with locally persisted data.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.shared.network.etp_trust import build_ssl_context, policy_from_environment

_HOST = "zakupki.gov.ru"
_FILE_PATH = "/44fz/filestore/public/1.0/download/priz/file.html"
_NOTICE_PATH = re.compile(r"/epz/order/notice/[a-z0-9-]+/view/documents\.html\Z")
_NUMBER = re.compile(r"(?:\d{11}|\d{19})\Z")
_UID = re.compile(r"[A-F0-9]{32}\Z")
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_FILE_BYTES = 24 * 1024 * 1024
MAX_ALL_BYTES = 64 * 1024 * 1024
MAX_FILES = 16


@dataclass(frozen=True)
class DocumentLink:
    uid: str
    title: str
    url: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: dict[str, str] | None = None
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.current = {"href": dict(attrs).get("href") or "", "text": ""}

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current is not None:
            a = self.current
            self.current = None
            self.links.append((a["href"], " ".join(a["text"].split())))


def _checked_url(url: str, *, attachment: bool) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != _HOST or parsed.fragment:
        raise ValueError("UNTRUSTED_EIS_URL")
    if attachment:
        if parsed.path != _FILE_PATH:
            raise ValueError("UNTRUSTED_FILESTORE_PATH")
        query = parse_qs(parsed.query, strict_parsing=True)
        if (
            set(query) != {"uid"}
            or len(query["uid"]) != 1
            or not _UID.fullmatch(query["uid"][0])
        ):
            raise ValueError("UNTRUSTED_FILE_UID")
    elif not _NOTICE_PATH.fullmatch(parsed.path):
        raise ValueError("INVALID_NOTICE_PAGE_PATH")
    return url


def public_documents_url(reg_number: str, notice_type: str) -> str:
    if not _NUMBER.fullmatch(reg_number) or not re.fullmatch(
        r"[a-z0-9]{2,12}", notice_type
    ):
        raise ValueError("INVALID_PROCUREMENT_REQUEST")
    return _checked_url(
        f"https://{_HOST}/epz/order/notice/{notice_type}/view/documents.html?"
        + urlencode({"regNumber": reg_number}),
        attachment=False,
    )


def parse_public_document_links(
    raw_page: bytes, *, page_url: str, reg_number: str
) -> tuple[list[DocumentLink], dict[str, Any]]:
    _checked_url(page_url, attachment=False)
    params = parse_qs(urlsplit(page_url).query, strict_parsing=True)
    if (
        set(params) != {"regNumber"}
        or params["regNumber"] != [reg_number]
        or not _NUMBER.fullmatch(reg_number)
    ):
        raise ValueError("NOTICE_NUMBER_MISMATCH")
    if not raw_page or len(raw_page) > MAX_PAGE_BYTES:
        raise ValueError("INVALID_PAGE_SIZE")
    parsed = _LinkParser()
    parsed.feed(raw_page.decode("utf-8", errors="replace"))
    body = " ".join(" ".join(parsed.text_parts).split())
    if reg_number not in body:
        raise ValueError("NOTICE_NUMBER_NOT_ON_PAGE")
    links: list[DocumentLink] = []
    seen: set[str] = set()
    for href, title in parsed.links:
        if _FILE_PATH not in href:
            continue
        url = _checked_url(urljoin(page_url, html.unescape(href)), attachment=True)
        uid = parse_qs(urlsplit(url).query)["uid"][0]
        if uid in seen:
            raise ValueError("DUPLICATE_FILE_UID")
        seen.add(uid)
        links.append(DocumentLink(uid=uid, title=title, url=url))
        if len(links) > MAX_FILES:
            raise ValueError("TOO_MANY_FILES")
    if not links:
        raise ValueError("NO_OFFICIAL_DOCUMENT_LINKS")
    m = re.search(r"Размещено\s+(\d{2}\.\d{2}\.\d{4})", body)
    metadata = {
        "procurement_number": reg_number,
        "page_url": page_url,
        "page_sha256": hashlib.sha256(raw_page).hexdigest(),
        "page_edition_ui_label": "Действующая"
        if re.search(r"Редакция\s+Действующая", body)
        else None,
        "page_posted_ui_date": m.group(1) if m else None,
        "proof_scope": "PUBLIC_PAGE_AND_ATTACHMENT_BYTES_ONLY",
        "independent_eis_revision_verified": False,
        "data_platform_identity_verified": False,
    }
    return links, metadata


class _SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _checked_url(newurl, attachment="/filestore/" in req.full_url)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, *, attachment: bool, max_size: int, opener: Any) -> bytes:
    _checked_url(url, attachment=attachment)
    with opener.open(
        Request(url, headers={"User-Agent": "Arvectum-Source-Receipt/1.0"}), timeout=25
    ) as result:
        _checked_url(result.geturl(), attachment=attachment)
        body = result.read(max_size + 1)
    if not body or len(body) > max_size:
        raise ValueError("INVALID_OR_OVERSIZED_CONTENT")
    if attachment and body.lstrip().lower().startswith((b"<html", b"<!doctype html")):
        raise ValueError("FILESTORE_RETURNED_HTML")
    return body


def fetch_public_original_receipts(
    *, reg_number: str, notice_type: str, opener: Any | None = None
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Return a manifest and original bytes for isolated caller-controlled storage.

    The manifest proves public retrieval and local hashing only. Does not
    manufacture DP resource IDs, source-revision proof, or business decisions.
    """
    url = public_documents_url(reg_number, notice_type)
    if opener is None:
        opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(context=build_ssl_context(_HOST, policy_from_environment())),
            _SafeRedirects(),
        )
    raw_page = _fetch(url, attachment=False, max_size=MAX_PAGE_BYTES, opener=opener)
    links, manifest = parse_public_document_links(
        raw_page, page_url=url, reg_number=reg_number
    )
    originals: dict[str, bytes] = {}
    receipts: list[dict[str, Any]] = []
    total_bytes = 0
    for link in links:
        binary = _fetch(
            link.url, attachment=True, max_size=MAX_FILE_BYTES, opener=opener
        )
        total_bytes += len(binary)
        if total_bytes > MAX_ALL_BYTES:
            raise ValueError("SOURCE_BUDGET_EXCEEDED")
        originals[link.uid] = binary
        receipts.append(
            {
                **asdict(link),
                "sha256": hashlib.sha256(binary).hexdigest(),
                "size_bytes": len(binary),
                "persisted_dp_resource_id": None,
                "persisted_dp_document_id": None,
            }
        )
    manifest["files"] = receipts
    manifest["total_bytes"] = total_bytes
    return manifest, originals
