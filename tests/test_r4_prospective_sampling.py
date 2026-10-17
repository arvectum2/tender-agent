"""Out-of-cohort source-only sampling tests. No model/legal labels involved."""
from __future__ import annotations

import copy

import pytest

from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    KNOWN_PAGES,
    preregister_sampling_intent,
    select_source_only_candidates,
    validate_sampling_intent,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    HoldoutLeakageError,
)

BEFORE = "2026-10-15T00:03:00+00:00"
AFTER = "2026-10-15T00:03:01+00:00"


def intent():
    return preregister_sampling_intent(
        registered_at_utc=BEFORE,
        existing_blind_lock_sha256="a" * 64,
        target_new_cases=3,
    )


def snapshots():
    return [
        {
            "url": KNOWN_PAGES[0],
            "status": "SOURCE_FETCH_VERIFIED",
            "captured_at_utc": AFTER,
            "rows": [
                {"visible_rank": 1, "registry_number": "9000000000000000001", "law": "44-ФЗ"},
                {"visible_rank": 2, "registry_number": "3000000000000000001", "law": "223-ФЗ"},
                {"visible_rank": 3, "registry_number": "9000000000000000002", "law": "44-ФЗ"},
            ],
        },
        {
            "url": KNOWN_PAGES[1],
            "status": "SOURCE_FETCH_VERIFIED",
            "captured_at_utc": AFTER,
            "rows": [
                {"visible_rank": 1, "registry_number": "9000000000000000002", "law": "44-ФЗ"},
                {"visible_rank": 2, "registry_number": "9000000000000000003", "law": "44-ФЗ"},
            ],
        },
    ]


def test_source_ranks_reproducible_and_44fz_only():
    result = select_source_only_candidates(
        intent=intent(), snapshots=snapshots(), forbidden_numbers=set(),
    )
    assert result["discovery_candidate_numbers"] == [
        "9000000000000000001", "9000000000000000002",
        "9000000000000000003",
    ]
    assert [v["reason"] for v in result["rejected_source_rows"]] == [
        "NOT_44FZ", "PRIOR_OR_DUPLICATE",
    ]
    assert result["official_original_eis_cases_verified"] == 0
    assert not result["sut_inference_authorized"]
    assert not result["bid_ready"]


def test_prior_hidden_cases_not_reselected_and_underfill_is_explicit():
    result = select_source_only_candidates(
        intent=intent(), snapshots=snapshots(),
        forbidden_numbers={"9000000000000000002"},
    )
    assert len(result["discovery_candidate_numbers"]) == 2
    assert result["selection_status"] == "UNDERFILLED_DISCOVERY_NO_UNREGISTERED_BACKFILL"


@pytest.mark.parametrize("corrupt", [
    lambda x: x[0].update(status="HTTP_404"),
    lambda x: x[0].update(captured_at_utc="2026-10-14T23:00:00+00:00"),
    lambda x: x[0]["rows"][0].update(visible_rank=2),
    lambda x: x.pop(),
])
def test_invalid_or_incomplete_snapshot_does_not_invent_cases(corrupt):
    source = snapshots()
    corrupt(source)
    with pytest.raises(ValueError):
        select_source_only_candidates(
            intent=intent(), snapshots=source, forbidden_numbers=set(),
        )


def test_unapproved_change_to_sampling_plan_fails_before_access():
    plan = intent()
    validate_sampling_intent(plan)
    changed = copy.deepcopy(plan)
    changed["target_new_cases"] = 20
    with pytest.raises(HoldoutLeakageError):
        validate_sampling_intent(changed)
    changed = copy.deepcopy(plan)
    changed["sut_inference_authorized"] = True
    with pytest.raises(HoldoutLeakageError):
        validate_sampling_intent(changed)
