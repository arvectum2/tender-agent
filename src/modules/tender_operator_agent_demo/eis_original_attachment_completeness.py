"""Fail-closed accounting of every published attachment in selected EIS XML.

The downloader can successfully obtain a contract and a specification while
other original notice files are missing. Keep analysis blocked in that case.
Never disclose filestore UIDs or raw links in public report fields.
"""
from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit


def _url_fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode("utf8")).hexdigest()


def expected_eis_notice_attachments(attachments: list[Any]) -> dict:
    hashes: set[str] = set()
    no_source_url = 0
    for item in attachments:
        url = getattr(item, "url", None)
        if not url:
            no_source_url += 1
            continue
        parts = urlsplit(str(url))
        if parts.scheme != "https" or parts.hostname not in {
            "zakupki.gov.ru", "int44.zakupki.gov.ru"
        } or parts.fragment or parts.username or parts.password:
            no_source_url += 1
            continue
        hashes.add(_url_fingerprint(str(url)))
    return {
        "source": "OFFICIAL_EIS_SELECTED_NOTICE_XML",
        "expected_link_count": len(hashes) + no_source_url,
        "valid_url_digests": sorted(hashes),
        "linkless_original_count": no_source_url,
        "live_notice_revision_confirmed": False,
    }


def check_eis_attachment_completeness(
    expected: dict,
    files: list[dict],
) -> dict:
    hashes = expected.get("valid_url_digests")
    if not isinstance(hashes, list) or any(
        not isinstance(x, str) or len(x) != 64 for x in hashes
    ) or len(set(hashes)) != len(hashes):
        raise ValueError("untrusted official source attachment inventory")
    announced = int(expected.get("expected_link_count", 0))
    unresolved = int(expected.get("linkless_original_count", 0))
    if announced != len(hashes) + unresolved or unresolved < 0:
        raise ValueError("official EIS attachment cardinality mismatch")
    present = set()
    for item in files:
        if item.get("source_type") != "notice_xml_attachments":
            continue
        url = item.get("source_url")
        if isinstance(url, str):
            present.add(_url_fingerprint(url))
    matched = present.intersection(hashes)
    missing = announced - len(matched)
    return {
        "official_original_attachments_announced": announced,
        "official_original_attachments_downloaded": len(matched),
        "official_original_attachments_missing": missing,
        "all_original_attachments_ready_for_analysis": (
            missing == 0 and announced > 0
        ),
        "live_notice_revision_confirmed": False,
    }
