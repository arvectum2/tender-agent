"""Readiness is not a frozen or accepted commercial corpus."""
import json

import pytest

from scripts.acceptance.apr06_review_readiness import POOL, inventory
from scripts.quality.apr067_corrected_cohort_integrity import (
    CORRECTED_PATH,
    ORIGINAL_PATH,
    CohortIntegrityError,
)
from src.modules.commercial_acceptance.acceptance import (
    METRICS,
    AcceptanceError,
    validate_manifest,
)


def inputs():
    return POOL.read_bytes(), ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes()


def test_pinned_inventory_reconciles_not_merges_corpus():
    result = inventory(*inputs())
    assert (result['candidate_count'], result['archived_development_count']) == (28, 20)
    assert (result['overlap_count'], result['candidate_only_count'], result['development_only_count']) == (16, 12, 4)
    assert len(result['cases']) == result['inventory_count_not_frozen_corpus'] == 32
    assert len({case['registry_number'] for case in result['cases']}) == 32
    assert result['human_reviews_present_in_inputs'] == 0
    assert result['commercial_metrics'] == dict.fromkeys(METRICS)
    assert not result['commercial_release_authorized']
    assert not result['current_source_verification_performed']
    for row in result['cases']:
        assert row['commercial_decision'] is row['attributed_human_review'] is None
        assert row['independently_verified_current_eis_revision'] is None
        if row['membership'] == 'DEVELOPMENT_ONLY':
            assert row['candidate_law'] is row['candidate_verification_state'] is None
        if row['membership'] == 'CANDIDATE_ONLY':
            assert row['archived_development_evidence'] is None
    with pytest.raises(AcceptanceError):
        validate_manifest(result, require_frozen=True)


@pytest.mark.parametrize('index', [0, 1, 2])
def test_any_changed_snapshot_fails_closed(index):
    sources = list(inputs())
    d = json.loads(sources[index])
    d['commercial_release_authorized'] = True
    sources[index] = json.dumps(d).encode()
    with pytest.raises(CohortIntegrityError):
        inventory(*sources)


def test_inventory_deterministic():
    assert inventory(*inputs()) == inventory(*inputs())
