"""Reviewer worksheet must never contain SUT predictions or fake labels."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_blind_reviewer_assignment import (
    REVIEW_CATEGORIES,
    build_source_only_assignment,
)


def _case():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("First-party source-only evaluator bundles live on Mac mini")
    p = (
        Path(root) / "ai-expert-20261014" / "semantic-holdout-prospective"
        / "blind-evaluator-packs"
    )
    f = next(iter(sorted(p.glob("*/evaluator_bundle.json"))), None)
    if f is None:
        pytest.skip("Current blind evaluator bundles unavailable")
    return json.loads(f.read_text())


def test_real_pre_sut_bundle_produces_unanswered_rubric():
    bundle = _case()
    doc = build_source_only_assignment(bundle)
    assert doc.count("SHA-256:") == len(bundle["documents"])
    assert len(REVIEW_CATEGORIES) == 8
    assert all(title in doc for title in REVIEW_CATEGORIES)
    assert "gold: **ОТСУТСТВУЕТ**" in doc
    assert "NOT_MEASURED" in doc
    assert "source_bundle_sha256" not in doc
    assert "confidence: 0.99" not in doc


def test_reviewer_bundle_refuses_leaked_analysis_keys():
    bundle = _case()
    contaminated = copy.deepcopy(bundle)
    contaminated["analysis"] = {"answer": "preselected legal outcome"}
    with pytest.raises(ValueError):
        build_source_only_assignment(contaminated)
    empty = copy.deepcopy(bundle)
    empty["documents"] = []
    with pytest.raises(ValueError):
        build_source_only_assignment(empty)
