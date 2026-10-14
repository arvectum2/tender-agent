"""Verify all stage2 discovery ranks against captured read-only HTML bytes.

A caller-supplied SOURCE_FETCH_VERIFIED flag is not evidence. This is a
source-identity check, NOT a legal/procurement verification or a proof that
the browser rendered every tender. Official getDocsIP validation follows.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.modules.benchmark_pipeline.contract import canonical_sha256
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    validate_sampling_intent,
)

SHA = re.compile(r"[0-9a-f]{64}\Z")
NOTICE = re.compile(r"(?<![0-9])[0-9]{19}(?![0-9])")


def check_live_discovery_evidence(
    *,
    intent: dict,
    capture_receipt: dict,
    captured_original_root: Path,
    parsed_snapshots: list[dict],
) -> str:
    """Return a fingerprint only for HTML-bound and rank-complete snapshots."""
    validate_sampling_intent(intent)
    if capture_receipt.get("intent_sha256") != intent["immutable_intent_sha256"]:
        raise ValueError("Live capture belongs to a different locked source plan")
    captured = capture_receipt.get("pages")
    if not isinstance(captured, list) or len(captured) != len(intent["page_order"]):
        raise ValueError("Both preregistered source pages must be captured")
    by_url = {item["url"]: item for item in parsed_snapshots}
    if len(by_url) != len(parsed_snapshots) or set(by_url) != set(intent["page_order"]):
        raise ValueError("All live discovery snapshots must use preregistered URLs")
    for rank, (url, receipt) in enumerate(zip(intent["page_order"], captured), 1):
        if (
            receipt.get("url") != url
            or receipt.get("source_page_rank") != rank
            or receipt.get("status") != "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED"
            or receipt.get("http_status") != 200
            or receipt.get("tls_context") != "STANDARD_CA_CERTIFICATE_VERIFICATION"
        ):
            raise ValueError("No independently captured TLS HTML for preregistered page")
        relative = Path(receipt.get("html_file") or "")
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Discovery HTML file location is unsafe")
        file = (captured_original_root / relative).resolve()
        if not file.is_relative_to(captured_original_root.resolve()) or not file.is_file():
            raise ValueError("Missing original discovery HTML")
        if file.is_symlink():
            raise ValueError("Symlink discovery source not allowed")
        content = file.read_bytes()
        digest = receipt.get("content_sha256")
        if not isinstance(digest, str) or not SHA.fullmatch(digest):
            raise ValueError("Missing original discovery HTML SHA")
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Original discovery HTML changed after capture")
        parsed = by_url[url]
        if parsed.get("status") != "SOURCE_FETCH_VERIFIED" or (
            parsed.get("source_capture_sha256") != digest
        ):
            raise ValueError("Parsed discovery IDs are not bound to original HTML")
        html_numbers = list(dict.fromkeys(NOTICE.findall(content.decode("utf8", errors="replace"))))
        parsed_numbers = [
            row.get("registry_number") for row in parsed.get("rows", [])
        ]
        if html_numbers != list(dict.fromkeys(parsed_numbers)):
            raise ValueError(
                "Missing, reordered, duplicated or fabricated discovery identifiers"
            )
        if len(parsed_numbers) != len(set(parsed_numbers)):
            raise ValueError("Repeated discovery notice ranks are not source-unique")
    return canonical_sha256(capture_receipt)
