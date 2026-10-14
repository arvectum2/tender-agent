"""Prospective source sampling cannot reuse older blind evidence."""
from __future__ import annotations

import pytest

from scripts.acceptance.select_r4_prospective_source_candidates import (
    select_officially_unverified_candidates,
)
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    KNOWN_PAGES,
    preregister_sampling_intent,
)
from tests.test_r4_semantic_holdout import baseline, make_lock


def test_prior_blind_notice_excluded_before_any_official_fetch():
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
         "captured_at_utc": "2026-10-15T01:00:00+00:00", "rows": []},
    ]
    report = select_officially_unverified_candidates(
        selection_intent=plan, current_private_snapshots=rows,
        development_audit=baseline(), earlier_blind_lock=prior,
    )
    assert report["discovery_candidate_numbers"] == ["9000000000000000009"]
    assert report["official_original_eis_cases_verified"] == 0
    assert report["selection_status"].startswith("UNDERFILLED")
    plan["prior_blind_lock_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        select_officially_unverified_candidates(
            selection_intent=plan, current_private_snapshots=rows,
            development_audit=baseline(), earlier_blind_lock=prior,
        )
