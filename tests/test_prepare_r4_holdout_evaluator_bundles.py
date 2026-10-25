"""Source-only blind evaluator manifests, using local first-party receipts."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from scripts.acceptance.prepare_r4_holdout_evaluator_bundles import (
    prepare_blind_bundles,
)


def _private():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("Private original bundle not mounted")
    base = Path(root) / "ai-expert-20261014" / "semantic-holdout-prospective"
    if not (base / "holdout-lock-private.json").is_file():
        pytest.skip("Prospective lock not present")
    lock = json.loads((base / "holdout-lock-private.json").read_text())
    candidates = json.loads((base / "blind-3-firstparty-candidates-private.json").read_text())
    return base, lock, candidates


def test_three_real_blind_evaluator_packs_source_only():
    root, lock, candidates = _private()
    packs = prepare_blind_bundles(
        lock, candidates, root, acquired_at=lock["locked_at_utc"]
    )
    assert len(packs) == 3
    assert sum(len(m["documents"]) for m, _ in packs) == 16
    assert all(
        m["source_bundle_sha256"] == b["source_bundle_sha256"]
        for m, b in packs
    )


def test_post_lock_source_or_cohort_change_fails_closed():
    root, lock, candidates = _private()
    altered = copy.deepcopy(candidates)
    altered[0]["documents"][0]["sha256"] = "a" * 64
    with pytest.raises(ValueError):
        prepare_blind_bundles(
            lock, altered, root, acquired_at=lock["locked_at_utc"]
        )
    with pytest.raises(ValueError):
        prepare_blind_bundles(
            lock, candidates[:2], root, acquired_at=lock["locked_at_utc"]
        )
