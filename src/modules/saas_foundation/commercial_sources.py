"""Pure commercial source identity; public source references are not verified facts."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

PATTERNS = {
    "workspace": ("workspace.ru", re.compile(r"/tenders/[a-z0-9-]+-(?P<id>[0-9]{4,7})/\Z")),
    "b2bcenter": ("www.b2b-center.ru", re.compile(r"/(?:app/market-next|market)/[a-z0-9-]+/tender-(?P<id>[0-9]{7})/\Z")),
}


def commercial_identity(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 650 or not url.startswith("https://") or any(c.isspace() for c in url):
        raise ValueError("Exact public commercial card URL required")
    parts = urlsplit(url)
    if parts.query or parts.fragment or parts.username or parts.password or parts.scheme != "https":
        raise ValueError("Unsupported commercial URL")
    for platform, (host, pattern) in PATTERNS.items():
        if parts.netloc == host and (match := pattern.fullmatch(parts.path)):
            return platform, match.group("id")
    raise ValueError("Unsupported commercial card identity")


# Exact public endpoints from the existing first-party source pipeline. No credentials.
INDEXES = {
    "workspace_rss": "https://workspace.ru/tenders/rss/",
    **{f"b2bcenter:{category}": f"https://www.b2b-center.ru/search/industry/{category}/"
       for category in ("razrabotka-sajtov", "crm-sistemy", "texpodderzhka", "razrabotka-mobilnogo-prilozheniya")},
}
MAX_INDEX_BYTES = 700_000


def read_index(index):
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args):
            raise ValueError("Unexpected index redirect")

    url = INDEXES[index]
    if index.startswith("b2bcenter:"):
        raise ValueError("B2B direct network access disabled; guarded adapter required")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Not original public index")
        mime = response.headers.get_content_type()
        allowed = {"text/html"} if index.startswith("b2bcenter:") else {"text/xml", "application/xml", "application/rss+xml"}
        if mime not in allowed:
            raise ValueError("Invalid public index MIME")
        return response.read(MAX_INDEX_BYTES + 1)


def parse_index(index, raw, keywords, exclusions, *, limit=10):
    import hashlib
    from xml.etree import ElementTree as ET

    from lxml import html

    if index not in INDEXES or not isinstance(raw, bytes) or not 100 < len(raw) <= MAX_INDEX_BYTES:
        raise ValueError("Invalid bounded index")
    platform = "workspace" if index == "workspace_rss" else "b2bcenter"
    rows = []
    if platform == "workspace":
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("XML declarations not allowed")
        tree = ET.fromstring(raw)
        if tree.tag != "rss" or tree.find("channel") is None:
            raise ValueError("Unexpected RSS layout")
        for row in tree.findall("./channel/item")[:100]:
            rows.append(((row.findtext("link") or "").strip(), " ".join((row.findtext("title") or "").split())))
    else:
        tree = html.fromstring(raw, parser=html.HTMLParser(no_network=True, encoding="utf-8"))
        for element in tree.xpath("//script|//style|//noscript|//svg"):
            element.drop_tree()
        for anchor in tree.xpath("//a[@href]")[:500]:
            url = anchor.get("href", "")
            try:
                if commercial_identity(url)[0] != platform:
                    continue
            except ValueError:
                continue
            parent = anchor
            for _ in range(8):
                if parent is None:
                    break
                excerpt = " ".join(parent.text_content().split())
                if len(excerpt) > 2200:
                    break
                if "Опубликовано:" in excerpt and "Подать заявку до:" in excerpt and "Закупка №" in excerpt:
                    identities = set()
                    for link in parent.xpath(".//a[@href]"):
                        try:
                            identities.add(commercial_identity(link.get("href", "")))
                        except ValueError:
                            continue
                    if identities == {commercial_identity(url)}:
                        rows.append((url, excerpt))
                    break
                parent = parent.getparent()
    candidates = {}
    for url, title in rows:
        try:
            actual, identifier = commercial_identity(url)
        except ValueError:
            continue
        if actual != platform or not title or not any(k.casefold() in title.casefold() for k in keywords) or any(k.casefold() in title.casefold() for k in exclusions):
            continue
        candidates.setdefault(identifier, {"source_platform": platform, "external_id": identifier,
            "source_url": url, "registry_number": None, "title": title[:500], "observed_price": None,
            "source": index, "source_verified": False, "human_review_required": True})
        if len(candidates) >= limit:
            break
    return {"outcome": "success_with_results" if candidates else "success_empty", "cards": list(candidates.values()),
            "source": index, "source_coverage_complete": False, "has_more": True,
            "index_sha256": hashlib.sha256(raw).hexdigest()}


def search_index(index, keywords, exclusions):
    return parse_index(index, read_index(index), keywords, exclusions)
