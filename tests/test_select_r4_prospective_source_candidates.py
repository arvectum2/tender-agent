"""Prospective source sampling cannot reuse older blind evidence."""
from __future__ import annotations

import copy
import hashlib

import pytest

from scripts.acceptance.select_r4_prospective_source_candidates import (
    select_officially_unverified_candidates,
)
from src.modules.tender_operator_agent_demo.r4_discovery_html_parser import (
    parse_source_cards,
)
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    KNOWN_PAGES,
    preregister_sampling_intent,
)
from tests.test_r4_semantic_holdout import baseline, make_lock


def test_prior_blind_notice_excluded_before_any_official_fetch(tmp_path):
    prior = make_lock()
    plan = preregister_sampling_intent(
        registered_at_utc="2026-10-15T00:00:00+00:00",
        existing_blind_lock_sha256=prior["immutable_lock_sha256"],
        target_new_cases=3,
    )
    rows = [
        {"url": KNOWN_PAGES[0], "status": "SOURCE_FETCH_VERIFIED",
         "captured_at_utc": "2026-10-15T01:00:00+00:00", "rows": [
             {"visible_rank": 1, "law": "44-ФЗ",
              "registry_number": "9000000000000000001"},
             {"visible_rank": 2, "law": "44-ФЗ",
              "registry_number": "9000000000000000009"},
         ]},
        {"url": KNOWN_PAGES[1], "status": "SOURCE_FETCH_VERIFIED",
         "captured_at_utc": "2026-10-15T01:00:00+00:00", "rows": [
             {"visible_rank": 1, "law": "44-ФЗ",
              "registry_number": "9000000000000000001"},
         ]},
    ]
    def build_original(numbers):
        return ("<html><body>" + "".join(
            f'<article class="tender-card"><span class="tag grad">44-ФЗ</span>'
            f'<h3><a href="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={no}">'
            'Tender</a></h3></article>'
            for no in numbers
        ) + "</body></html>").encode()

    originals = [
        build_original(["9000000000000000001", "9000000000000000009"]),
        build_original(["9000000000000000001"]),
    ]
    capture = {"intent_sha256": plan["immutable_intent_sha256"], "pages": []}
    for n, (snapshot, raw) in enumerate(zip(rows, originals), 1):
        path = tmp_path / f"page-{n}.html"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        snapshot["rows"] = parse_source_cards(raw)
        snapshot["source_capture_sha256"] = digest
        capture["pages"].append({
            "url": snapshot["url"], "source_page_rank": n,
            "status": "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED",
            "http_status": 200,
            "tls_context": "STANDARD_CA_CERTIFICATE_VERIFICATION",
            "content_sha256": digest, "html_file": path.name,
        })
    kwargs = {
        "selection_intent": plan, "current_private_snapshots": rows,
        "development_audit": baseline(), "earlier_blind_lock": prior,
        "original_capture_receipt": capture,
        "captured_original_root": tmp_path,
    }
    report = select_officially_unverified_candidates(**kwargs)
    assert report["discovery_candidate_numbers"] == ["9000000000000000009"]
    assert report["official_original_eis_cases_verified"] == 0
    assert report["selection_status"].startswith("UNDERFILLED")
    plan["prior_blind_lock_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        select_officially_unverified_candidates(**kwargs)
    kwargs["selection_intent"] = copy.deepcopy(plan)
    kwargs["selection_intent"]["target_new_cases"] = 7
    # Changing the registered sample quota must not be silently accepted.
    with pytest.raises(ValueError):
        select_officially_unverified_candidates(**kwargs)
