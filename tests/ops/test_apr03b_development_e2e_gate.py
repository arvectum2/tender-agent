"""Owner-accepted ChatGPT expertise must never become fabricated human gold."""

from __future__ import annotations

import copy

import pytest

from scripts.acceptance.apr03b_development_e2e_gate import _REQUIRED, evaluate


def _receipt():
    return {
        "stage": "development_e2e",
        "reviewer_kind": "owner_delegated_chatgpt",
        "reviewer_source_facts_checked": True,
        "notice_number": "0372200172326000015",
        "run_id": "toa-run-20261012200402-7249ed",
        "report_sha256": "b" * 64,
        "official_originals": [
            {"original_name": "notice.xml", "sha256": "a" * 64, "verified_from_official": True}
        ],
        "steps": {name: {"passed": True, "evidence_ref": f"evidence:{name}"} for name in _REQUIRED},
        "citation_audit": {"verified_fact_claims": 3, "unsupported_material_claims": 0},
        "analysis_mode": "llm_tender_operator_provider",
        "current_official_revision_verified": False,
        "archival_export_http_status": 409,
        "critical_workflow_defects": 0,
        "bid_submitted": False,
        "digital_signature_used": False,
        "payment_created": False,
        "production_mutated": False,
        "etp_mutated": False,
        "owner_legal_go_granted": False,
    }


def test_development_e2e_accepts_delegated_ai_expert_without_human_gold():
    verified = _receipt()
    assert "human_gold" not in verified
    verdict = evaluate(verified)
    assert verdict["accepted"] is True
    assert verdict["not_a_human_gold_label"] is True
    assert verdict["grants_bid_authority"] is False


@pytest.mark.parametrize("step", _REQUIRED)
def test_all_e2e_workflow_steps_are_mandatory(step):
    verified = _receipt()
    verified["steps"][step]["passed"] = False
    assert f"e2e_step_not_proven:{step}" in evaluate(verified)["reasons"]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"reviewer_kind": "independent_human_gold"}, "missing_owner_delegated_ai_review"),
        ({"reviewer_source_facts_checked": False}, "expert_source_review_not_attested"),
        ({"official_originals": []}, "missing_original_source_files"),
        ({"citation_audit": {"verified_fact_claims": 0, "unsupported_material_claims": 0}}, "material_claim_citations_not_verified"),
        ({"citation_audit": {"verified_fact_claims": 2, "unsupported_material_claims": 1}}, "material_claim_citations_not_verified"),
        ({"analysis_mode": "fallback_deterministic_adapter"}, "full_model_analysis_not_proven"),
        ({"archival_export_http_status": 200}, "archival_export_fail_closed_not_proven"),
        ({"critical_workflow_defects": 1}, "critical_workflow_defects_open"),
        ({"bid_submitted": True}, "procurement_or_production_boundary_not_proven"),
        ({"owner_legal_go_granted": True}, "procurement_or_production_boundary_not_proven"),
    ],
)
def test_fail_closed_on_missing_proofs(change, reason):
    receipt = _receipt()
    receipt.update(change)
    assert reason in evaluate(receipt)["reasons"]


def test_wrong_sha_and_claim_types_never_pass():
    receipt = _receipt()
    receipt["official_originals"][0]["sha256"] = "none"
    receipt["citation_audit"]["verified_fact_claims"] = True
    verdict = evaluate(receipt)
    assert not verdict["accepted"]
    assert "unverified_original_source" in verdict["reasons"]
    assert "material_claim_citations_not_verified" in verdict["reasons"]


def test_missing_required_security_field_does_not_default_to_safe():
    receipt = copy.deepcopy(_receipt())
    del receipt["etp_mutated"]
    assert not evaluate(receipt)["accepted"]
