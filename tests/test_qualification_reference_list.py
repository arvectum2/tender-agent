"""Versioned user reference-list and source-bound competitive NO_GO regression."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.modules.company_profile_store.qualification_references import (
    CompletedContractReferenceSnapshot,
    QualificationCriterion,
    assess_references,
)

CASE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/acceptance/arvectum_owner_reference_list_and_czn_2026-10-13.json"
    ).read_text(encoding="utf-8")
)


def _criterion(**overrides) -> QualificationCriterion:
    return QualificationCriterion.model_validate({
        **CASE["czn_source_bound_criterion"], **overrides,
    })


def _snapshot(contracts=None, **overrides) -> CompletedContractReferenceSnapshot:
    value = {**CASE["reference_fact_value"], **overrides}
    if contracts is not None:
        value["contracts"] = contracts
    return CompletedContractReferenceSnapshot.model_validate(value)


def _contract(*, law="44fz", subject="website", chatbot=True, completed=True,
              signed="2026-10-02", act="s3://signed-act-1", contract_ref="s3://contract-1",
              number="ABC"):
    return {
        "law": law, "contract_number": number, "subject": subject,
        "chatbot_in_scope": chatbot, "completed": completed,
        "acceptance_signed_at": signed,
        "contract_document_ref": contract_ref,
        "signed_final_act_ref": act,
    }


def test_owner_confirmed_zero_references_gives_czn_competitive_no_go_not_legal_denial():
    result = assess_references(
        customer_id="arvectum-tenant", criterion=_criterion(),
        snapshot=_snapshot(),
        fact_version=1, fact_source_type="CUSTOMER_PROVIDED",
        fact_source_ref="owner-user-confirmed-2026-10-13",
    )
    assert result.reference_list_state == "CONFIRMED_COMPLETE"
    assert result.qualifying_contracts == 0
    assert result.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"
    assert result.eligibility_status == "NOT_ASSESSED"
    assert result.technical_feasibility_status == "NOT_ASSESSED"
    assert result.predicted_win_probability is None
    assert result.customer_owner_approval is False
    assert result.human_gold is False
    assert result.external_action_allowed is False
    assert result.procurement_notice_version == 4
    assert result.criterion["qualification_weight_percent"] == 70
    assert result.criterion["price_weight_percent"] == 30


def test_missing_or_partial_references_are_not_silently_treated_as_zero():
    for snapshot, expired, recommendation in (
        (None, False, "QUALIFICATION_EVIDENCE_UNKNOWN"),
        (_snapshot(completeness="PARTIAL"), False, "QUALIFICATION_EVIDENCE_PARTIAL"),
        (_snapshot(), True, "QUALIFICATION_EVIDENCE_EXPIRED"),
        (_snapshot(owner_confirmed=False, completeness="PARTIAL"), False, "QUALIFICATION_EVIDENCE_UNKNOWN"),
    ):
        result = assess_references(
            customer_id="tenant-1", criterion=_criterion(),
            snapshot=snapshot, expired=expired,
        )
        assert result.recommendation == recommendation
        assert result.qualifying_contracts is None
        assert result.external_action_allowed is False


def test_qualifying_44fz_or_223fz_completed_chatbot_with_documents():
    for law in ("44fz", "223fz"):
        out = assess_references(
            customer_id="a", criterion=_criterion(),
            snapshot=_snapshot([_contract(law=law)]),
        )
        assert out.qualifying_contracts == 1
        assert out.recommendation == "QUALIFYING_REFERENCES_PRESENT_REVIEW_SCORE"


@pytest.mark.parametrize("contract", [
    _contract(law="44fz", chatbot=False),
    _contract(law="44fz", completed=False),
    _contract(law="223fz", signed="2016-01-01"),
    _contract(law="223fz", signed="2026-10-15"),
    _contract(law="223fz", subject="module", chatbot=False),
])
def test_unrelated_or_unfinished_work_does_not_count(contract):
    result = assess_references(
        customer_id="a", criterion=_criterion(),
        snapshot=_snapshot([contract]),
    )
    assert result.qualifying_contracts == 0
    assert result.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"


def test_unsigned_or_forged_complete_contract_rejected():
    for row in (_contract(act=None), _contract(contract_ref=None)):
        with pytest.raises(ValueError):
            _snapshot([row])


def test_a_smaller_qualification_weight_is_risk_not_automatic_no_go():
    result = assess_references(
        customer_id="a", criterion=_criterion(
            qualification_weight_percent=30, price_weight_percent=70,
        ), snapshot=_snapshot(),
    )
    assert result.qualifying_contracts == 0
    assert result.recommendation == "COMPETITIVE_RISK_NOT_AUTOMATIC_NO_GO"


def test_invalid_source_rev_document_checksum_or_weights_rejected():
    for overrides in (
        {"procurement_number": "not-a-real-registry"},
        {"source_document_uid": "NOT_UID"},
        {"source_document_sha256": "not-sha"},
        {"qualification_weight_percent": 80},
        {"procurement_notice_version": 0},
    ):
        with pytest.raises(ValueError):
            _criterion(**overrides)


def test_duplicate_evidence_and_unconfirmed_complete_zero_rejected():
    with pytest.raises(ValueError):
        _snapshot(owner_confirmed=False)
    with pytest.raises(ValueError):
        _snapshot([_contract(), _contract()])


def _customer(client, name: str) -> str:
    response = client.post(
        "/customers",
        json={
            "legal_name": name,
            "inn": None,
            "kpp": None,
            "customer_status": "PROSPECT",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["customer_id"]


def _post_reference(client, customer_id, reference=None, *, expires_at=None):
    payload = {
        "fact_group": "EXPERIENCE",
        "value": CASE["reference_fact_value"] if reference is None else reference,
        "source_type": "CUSTOMER_PROVIDED",
        "source_ref": "OWNER_USER_STATEMENT_2026-10-13",
        "expires_at": expires_at,
    }
    return client.post(
        f"/api/company-profile/customers/{customer_id}/facts/completed_contract_reference_list/versions",
        json=payload,
    )


def _assess(client, customer_id: str, criterion=None):
    return client.post(
        f"/api/company-profile/customers/{customer_id}/qualification/assess",
        json=criterion or CASE["czn_source_bound_criterion"],
    )


def test_api_reads_latest_version_qualified_empty_and_tenant_isolated(client):
    tenant_a = _customer(client, "Reference A")
    tenant_b = _customer(client, "Reference B")
    missing = _assess(client, tenant_a)
    assert missing.status_code == 200, missing.text
    assert missing.json()["recommendation"] == "QUALIFICATION_EVIDENCE_UNKNOWN"
    saved = _post_reference(client, tenant_a)
    assert saved.status_code == 201, saved.text
    assert saved.json()["version_no"] == 1
    assessed = _assess(client, tenant_a)
    assert assessed.status_code == 200, assessed.text
    data = assessed.json()
    assert data["customer_id"] == tenant_a
    assert data["reference_fact_version"] == 1
    assert data["recommendation"] == "NO_GO_QUALIFICATION_COMPETITIVENESS"
    assert data["external_action_allowed"] is False
    other = _assess(client, tenant_b)
    assert other.status_code == 200
    assert other.json()["recommendation"] == "QUALIFICATION_EVIDENCE_UNKNOWN"
    assert _assess(client, "not-present").status_code == 404


def test_api_latest_supersedes_original_zero_without_cross_tenant(client):
    cid = _customer(client, "Updated Owner")
    assert _post_reference(client, cid).status_code == 201
    updated = _post_reference(client, cid, _snapshot([_contract()]).model_dump(mode="json"))
    assert updated.status_code == 201, updated.text
    assert updated.json()["version_no"] == 2
    decision = _assess(client, cid)
    assert decision.status_code == 200, decision.text
    assert decision.json()["qualifying_contracts"] == 1
    assert decision.json()["recommendation"] == "QUALIFYING_REFERENCES_PRESENT_REVIEW_SCORE"
    history = client.get(f"/api/company-profile/customers/{cid}/facts/completed_contract_reference_list")
    assert [x["version_no"] for x in history.json()] == [1, 2]


def test_api_expired_snapshot_not_promoted_to_zero(client):
    cid = _customer(client, "Expired Reference")
    saved = _post_reference(client, cid, expires_at="2025-01-01T00:00:00Z")
    assert saved.status_code == 201
    out = _assess(client, cid)
    assert out.status_code == 200, out.text
    assert out.json()["recommendation"] == "QUALIFICATION_EVIDENCE_EXPIRED"
    assert out.json()["qualifying_contracts"] is None


def test_api_disallows_unverified_source_to_justify_competitive_no_go(client):
    cid = _customer(client, "AI guessed")
    saved = client.post(
        f"/api/company-profile/customers/{cid}/facts/completed_contract_reference_list/versions",
        json={
            "fact_group": "EXPERIENCE",
            "value": CASE["reference_fact_value"],
            "source_type": "AI_INFERRED",
            "source_ref": "auto-generated",
        },
    )
    assert saved.status_code == 201, saved.text
    result = _assess(client, cid)
    assert result.status_code == 200
    assert result.json()["recommendation"] == "QUALIFICATION_EVIDENCE_UNKNOWN"
