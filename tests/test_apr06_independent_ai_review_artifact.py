"""Proof contract: independent AI audit must not become fabricated human acceptance."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/acceptance/apr06_independent_gpt6_audit_2026-10-09.json"


def _audit() -> dict:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_only_model_review_never_human_label_or_commercial_pass():
    data = _audit()
    assert data["schema_version"] == "apr06-independent-gpt6-audit-v1"
    assert data["reviewer_type"] == "separate_gpt6_model_assessment_over_rdc"
    assert data["human_operator_review"] is False
    assert data["human_signed_decisions"] == 0
    assert data["final_commercial_acceptance"] is False
    assert len(data["cases"]) == 9
    assert all(c["human_confirmed"] is False and c["external_action_allowed"] is False
               for c in data["cases"])


def test_review_comparisons_follow_source_revisions_and_do_not_invent_go():
    data = _audit()
    cases = {c["reg_number"]: c for c in data["cases"]}
    assert len(cases) == 9
    assert Counter(c["model_independent_recommendation"] for c in cases.values()) == {
        "NO_GO": 6, "DEFER": 3,
    }
    assert all(c["machine_decision"] in {"NO_GO", "NEEDS_REVIEW"} for c in cases.values())
    assert cases["0158300034526000388"]["machine_decision"] == "NO_GO"
    assert cases["0158300034526000388"]["latest_archived_notice"]["version"] == 5
    assert cases["0158300034526000388"]["latest_archived_notice"]["source_deadline"] == "2026-10-12T08:00:00+03:00"
    assert cases["0348100024426000039"]["latest_archived_notice"]["version"] == 3
    assert cases["0348100024426000039"]["latest_archived_notice"]["source_deadline"] == "2026-10-19T10:00:00+03:00"
    assert all(re.fullmatch(r"[0-9a-f]{64}", c["latest_archived_notice"]["source_sha256"])
               for c in cases.values())


def test_ai_audit_does_not_claim_full_legal_or_citation_ground_truth():
    data = _audit()
    assert len(data["critical_mismatches"]) == 2
    for item in data["cases"]:
        assert "not a full legal/commercial" in item["model_source_read_scope"]
        assert item["source_files_total"] >= item["source_text_flagged_available"]
        assert item["spec_and_contract_source_hashes"]
        for attachment in item["spec_and_contract_source_hashes"]:
            assert re.fullmatch(r"[a-f0-9]{64}", attachment["sha256"])
