"""Metadata-only source provenance for already fetched Tender Agent web pages.

Existing canonical DB only. No network calls, raw page/chat storage, customer
data, bid eligibility, human/legal gold or inference from an untrusted page.

The caller appends inside its page-save transaction: commit both or neither.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from urllib.parse import urlsplit

from src.modules.procurement_learning_corpus.service import make_manual_candidate

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_HTML = 4 * 1024 * 1024


def _safe_public_host(url: object) -> str | None:
    if not isinstance(url, str) or len(url) > 1024:
        return None
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
            or not hostname
            or len(hostname) > 253
            or "." not in hostname
            or not hostname.isascii()
        ):
            return None
        if hostname.lower().endswith((".local", ".internal", ".test", ".invalid")):
            return None
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return None
        if not re.fullmatch(r"[a-z0-9.-]+", hostname.lower()):
            return None
        return hostname.lower()
    except ValueError:
        return None


def make_fetched_web_source_candidate(
    procurement_ref: str, fetch: object
) -> dict | None:
    """Return conservative unreviewed metadata after public HTTPS HTML 200.

    A missing candidate means the web page remains in the normal Tender Agent
    web corpus but is NOT eligible for source-backed LLM intake.
    """
    if not isinstance(procurement_ref, str) or not 0 < len(procurement_ref) <= 256:
        return None
    if (
        getattr(fetch, "status", None) != "fetched"
        or getattr(fetch, "http_status", None) != 200
        or not isinstance(getattr(fetch, "html", None), str)
        or not 0 < len(fetch.html.encode("utf-8")) <= _MAX_HTML
    ):
        return None
    source_host = _safe_public_host(getattr(fetch, "url", None))
    final_host = _safe_public_host(getattr(fetch, "final_url", None))
    if not source_host or not final_host or source_host != final_host:
        return None
    mime = str(getattr(fetch, "content_type", "")).lower().split(";")[0].strip()
    if mime != "text/html":
        return None
    # This is a SHA of decoded HTML exposed by the fetcher; it is not a
    # cryptographic attestation of the remote server's raw HTTP bytes.
    html_sha = hashlib.sha256(fetch.html.encode("utf-8")).hexdigest()
    url_sha = hashlib.sha256(fetch.url.encode("utf-8")).hexdigest()
    record_key = hashlib.sha256(
        (procurement_ref + ":" + url_sha + ":" + html_sha).encode("utf-8")
    ).hexdigest()
    source_url_hash = getattr(fetch, "url_hash", None)
    if not isinstance(source_url_hash, str) or not _SHA256.fullmatch(source_url_hash):
        source_url_hash = url_sha
    event = {
        "event_id": "ta-web-fetched:" + record_key[:40],
        "procurement_ref": procurement_ref,
        "participation": "reviewed_only",
        "review_state": "system_recorded",
        "source_role": "development_exposed",
        "event_type": "canonical_tender_research_web_page_fetched",
        "source_platform": "tender_agent_public_web_pipeline",
        "source_host": source_host,
        "source_url_sha256": url_sha,
        "source_url_hash_in_web_store": source_url_hash,
        "source_decoded_html_sha256": html_sha,
        "source_html_bytes": len(fetch.html.encode("utf-8")),
        "source_http_status": 200,
        "source_content_type": "text/html",
        "original_source_verification_gate": (
            "PUBLIC_FETCH_ONLY_NOT_OFFICIAL_PROVENANCE"
        ),
        "procurement_legal_status_verified": False,
        "supplier_eligibility_verified": False,
        "owner_bid_go": False,
        "human_verified_interpretation": False,
        "training_labels": "NOT_REVIEWED",
        "raw_web_html_copied": False,
        "raw_web_text_copied": False,
        "private_customer_data_copied": False,
    }
    return make_manual_candidate(event)
