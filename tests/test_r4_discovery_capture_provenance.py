"""Synthetic signed-offline HTML source bytes, never EIS legal gold."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_discovery_html_parser import (
    parse_source_cards,
)
from src.modules.tender_operator_agent_demo.r4_discovery_snapshot_provenance import (
    check_live_discovery_evidence,
)
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    KNOWN_PAGES,
    preregister_sampling_intent,
)


def fixture(tmp_path: Path):
    intent = preregister_sampling_intent(
        registered_at_utc="2026-10-15T00:00:00+00:00",
        existing_blind_lock_sha256="a" * 64,
        target_new_cases=3,
    )
    notice = ["9000000000000000009", "9000000000000000010"]
    captures, parsed = [], []
    for rank, url in enumerate(KNOWN_PAGES, 1):
        ids = notice if rank == 1 else [notice[0]]
        cards = "".join(
            f'<article class="tender-card"><div class="tags"><span class="tag grad">44-ФЗ</span></div>'
            f'<h3><a href="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={no}">'
            'Source item</a></h3></article>'
            for no in ids
        )
        html = ("<html><body>" + cards + "</body></html>").encode()
        file = tmp_path / f"page{rank}.html"
        file.write_bytes(html)
        digest = hashlib.sha256(html).hexdigest()
        captures.append({
            "url": url, "source_page_rank": rank,
            "capture_started_at_utc": "2026-10-15T01:00:00+00:00",
            "status": "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED",
            "http_status": 200, "tls_context": "STANDARD_CA_CERTIFICATE_VERIFICATION",
            "html_file": file.name, "content_sha256": digest,
        })
        parsed.append({
            "url": url, "status": "SOURCE_FETCH_VERIFIED",
            "captured_at_utc": "2026-10-15T01:00:00+00:00",
            "source_capture_sha256": digest,
            "rows": parse_source_cards(html),
        })
    return {
        "intent": intent,
        "capture_receipt": {"intent_sha256": intent["immutable_intent_sha256"], "pages": captures},
        "parsed_snapshots": parsed,
        "captured_original_root": tmp_path,
    }


def test_sources_are_bound_to_local_bytes_and_pinned_page_ranks(tmp_path):
    f = fixture(tmp_path)
    assert len(check_live_discovery_evidence(**f)) == 64


@pytest.mark.parametrize("change", [
    lambda f: f["parsed_snapshots"][0]["rows"][0].update(registry_number="9000000000000000042"),
    lambda f: f["parsed_snapshots"][0]["rows"].reverse(),
    lambda f: f["parsed_snapshots"][0].update(source_capture_sha256="b" * 64),
    lambda f: f["capture_receipt"]["pages"][0].update(http_status=404),
    lambda f: f["capture_receipt"]["pages"][0].update(html_file="../outside.html"),
    lambda f: f["capture_receipt"]["pages"].pop(),
])
def test_fabricated_ranks_binary_or_transport_attestation_fail_closed(tmp_path, change):
    f = fixture(tmp_path)
    change(f)
    with pytest.raises(ValueError):
        check_live_discovery_evidence(**f)


def test_modified_original_after_capture_is_rejected(tmp_path):
    f = fixture(tmp_path)
    original = tmp_path / f["capture_receipt"]["pages"][0]["html_file"]
    original.write_bytes(original.read_bytes() + b"not original anymore")
    with pytest.raises(ValueError, match="changed"):
        check_live_discovery_evidence(**f)


def test_missing_source_both_pages_and_modified_plan_fails(tmp_path):
    f = fixture(tmp_path)
    f["parsed_snapshots"].pop()
    with pytest.raises(ValueError):
        check_live_discovery_evidence(**f)
    f = fixture(tmp_path)
    f["intent"] = copy.deepcopy(f["intent"])
    f["intent"]["target_new_cases"] = 8
    with pytest.raises(ValueError):
        check_live_discovery_evidence(**f)
