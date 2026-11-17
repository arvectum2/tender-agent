"""Offline candidate inventory from a previously reverified commercial HTML snapshot.

Not a download allowlist, not original document evidence and never complete coverage.
Unknown/opaque links are not resolved or requested.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlsplit

from lxml import html

from src.modules.saas_foundation.commercial_card_evidence import MAX_CARD_BYTES
from src.modules.saas_foundation.commercial_sources import commercial_identity

MAX_LINKS = 500
MAX_CANDIDATES = 20
_FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|txt|rtf|csv)$", re.IGNORECASE)
# Deliberately narrow: ambiguous escaping, queries, credentials and fragments are not accepted.
_SAFE_PATH = re.compile(r"/[A-Za-z0-9._~/-]+\Z")


def attachment_inventory(source_url: str, original: bytes) -> dict:
    commercial_identity(source_url)
    if not isinstance(original, bytes) or not 0 < len(original) <= MAX_CARD_BYTES:
        raise ValueError("Invalid saved card bytes")
    root = html.fromstring(original.decode("utf-8", errors="strict"), parser=html.HTMLParser(no_network=True))
    for node in root.xpath('//script|//style|//noscript|//svg|//template|//*[@hidden or @aria-hidden="true"]'):
        if node.getparent() is not None:
            node.drop_tree()
    links = root.xpath('//body//a[@href]')
    base_present = bool(root.xpath('//base[@href]'))
    candidates = {}
    rejected = 0
    for link in links[:MAX_LINKS]:
        href = link.get('href', '').strip()
        try:
            parts = urlsplit(href)
        except ValueError:
            if 'download' in link.attrib:
                rejected += 1
            continue
        suffix = _FILE.search(parts.path)
        if not suffix and 'download' not in link.attrib:
            continue
        if (base_present or not suffix or len(href) > 650 or any(c.isspace() for c in href)
                or parts.query or parts.fragment or parts.username or parts.password
                or (parts.scheme and parts.scheme != 'https') or href.startswith('//')
                or not _SAFE_PATH.fullmatch(parts.path) or '//' in parts.path
                or any(n in {'.', '..'} for n in parts.path.split('/'))):
            rejected += 1
            continue
        url = urljoin(source_url, href)
        target = urlsplit(url)
        if target.scheme != 'https' or target.netloc != urlsplit(source_url).netloc:
            rejected += 1
            continue
        if url not in candidates and len(candidates) < MAX_CANDIDATES:
            label = ' '.join(link.text_content().split())[:200]
            candidates[url] = {'candidate_id': hashlib.sha256(url.encode()).hexdigest(), 'source_url': url, 'display_label': label or None, 'format_hint': suffix.group(1).lower(),
                               'original_bytes_verified': False, 'download_allowed': False}
        elif url not in candidates:
            rejected += 1
    return {'candidates': list(candidates.values()), 'rejected_or_opaque_links': rejected,
            'scanned_links': min(len(links), MAX_LINKS), 'link_scan_truncated': len(links) > MAX_LINKS,
            'candidate_limit': MAX_CANDIDATES, 'full_documents_verified': False,
            'coverage_complete': False, 'download_enabled': False}
