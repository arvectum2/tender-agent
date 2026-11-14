"""Parse explicitly published GPB document links; no inferred endpoints."""
from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

DOCUMENT_PATH = re.compile(
    r"/file/get/t/(?:LotDocuments/id/[0-9]+|PriceOrderDocument/id/[0-9]+/m/nsi)"
    r"/name/[a-f0-9]+\.[0-9]+"
)


def valid_document_url(url):
    u = urlsplit(url)
    return (u.scheme == "https" and u.netloc == "etp.gpb.ru"
            and not u.query and not u.fragment and bool(DOCUMENT_PATH.fullmatch(u.path)))


class Documents(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and "procedureDocItem__title" in d.get("class", "").split():
            self.current = [d.get("href", ""), []]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            url, parts = self.current
            self.rows.append((url, " ".join("".join(parts).split())))
            self.current = None


def parse_document_links(raw, *, detail_url, external_id):
    u = urlsplit(detail_url)
    prefix, native_id = external_id.split(":", 1)
    if (u.scheme != "https" or u.netloc not in {"etpgpb.ru", "new.etpgpb.ru"}
            or prefix not in {"etp", "price_request"} or not native_id.isdecimal()
            or not u.path.startswith(f"/procedures/{prefix}/{native_id}-")
            or len(raw) > 4_000_000):
        raise ValueError("unverified procedure identity or source")
    p = Documents()
    p.feed(raw.decode("utf-8"))
    p.close()
    rows = []
    for url, name in p.rows:
        if not valid_document_url(url) or not name or len(name) > 512:
            raise ValueError("invalid published document anchor")
        rows.append({"source": "etp_gpb", "external_id": external_id,
                     "detail_url": detail_url, "detail_sha256": hashlib.sha256(raw).hexdigest(),
                     "document_url": url, "original_filename": name,
                     "verification": "PUBLISHED_LINK_ONLY"})
    if len({r["document_url"] for r in rows}) != len(rows):
        raise ValueError("duplicate document anchor")
    return rows
