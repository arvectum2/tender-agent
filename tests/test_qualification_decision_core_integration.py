"""Source-bound reference-list evaluation participates in Tender Agent Decision Core."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SOURCE = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/acceptance/arvectum_owner_reference_list_and_czn_2026-10-13.json"
).read_text(encoding="utf-8"))


def _customer(client, company: str):
    result = client.post("/customers", json={
        "legal_name": company, "inn": None, "kpp": None, "customer_status": "PROSPECT",
    })
    assert result.status_code == 201, result.text
    return result.json()["customer_id"]


def _post_zero(client, cid):
    response = client.post(
        f"/api/company-profile/customers/{cid}/facts/completed_contract_reference_list/versions",
        json={
            "fact_group": "EXPERIENCE",
            "value": SOURCE["reference_fact_value"],
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": SOURCE["reference_fact_source_ref"],
        },
    )
    assert response.status_code == 201, response.text


def _request(**changes):
    criterion = SOURCE["czn_source_bound_criterion"]
    source = {
        "procurement_number": criterion["procurement_number"],
        "notice_version": criterion["procurement_notice_version"],
        "document_uid": criterion["source_document_uid"],
        "document_sha256": criterion["source_document_sha256"],
    }
    model = {
        "procurement_law": "44fz", "procurement_number": criterion["procurement_number"],
    }
    return {
        "criterion": criterion,
        "procurement_model": changes.get("procurement_model", model),
        "source_binding": changes.get("source_binding", source),
    }


def _decision(client, customer_id, body):
    return client.post(
        f"/api/company-profile/customers/{customer_id}/qualification/decision-core",
        json=body,
    )


def test_czn_zero_completed_contracts_wires_no_go_without_legal_disqualification(client):
    cid = _customer(client, "Arvectum qualification")
    _post_zero(client, cid)
    resp = _decision(client, cid, _request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["competitive_recommendation"] == "NO_GO"
    assert data["assessment"]["recommendation"] == "NO_GO_QUALIFICATION_COMPETITIVENESS"
    assert data["assessment"]["qualifying_contracts"] == 0
    assert data["decision_core"]["decision"]["competitive_recommendation"] == "NO_GO"
    # The existing core still says review: no false hard legal blocker.
    assert data["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert data["assessment"]["eligibility_status"] == "NOT_ASSESSED"
    assert data["decision_core"]["safety"]["bid_submission_allowed"] is False
    assert data["external_action_allowed"] is False


def test_other_tenant_without_reference_list_is_unknown_not_zero(client):
    owner = _customer(client, "Reference first")
    other = _customer(client, "Reference other")
    _post_zero(client, owner)
    result = _decision(client, other, _request())
    assert result.status_code == 200
    assert result.json()["competitive_recommendation"] == "HUMAN_REVIEW_REQUIRED"
    assert result.json()["assessment"]["qualifying_contracts"] is None


@pytest.mark.parametrize("changes", [
    {"source_binding": {}},
    {"source_binding": {
        "procurement_number": "0348100024426000039",
        "notice_version": 3,
        "document_uid": "01A0F10655C27A35B5A5A70090D2BB1A",
        "document_sha256": "bda1eff35bffda97f5a8e661f5d9fd5d221562e2b00e55feec28cb3fbd745dd8",
    }},
    {"procurement_model": {
        "procurement_number": "0372200172326000015", "procurement_law": "44fz",
    }},
    {"procurement_model": {
        "procurement_number": "0348100024426000039", "procurement_law": "223fz",
    }},
])
def test_mismatch_of_original_eis_revision_number_or_law_rejected(client, changes):
    cid = _customer(client, "Mismatch source")
    _post_zero(client, cid)
    response = _decision(client, cid, _request(**changes))
    assert response.status_code in (400, 422), response.text


def test_competitive_no_go_does_not_overwrite_known_legal_hard_blocker(client):
    cid = _customer(client, "Legally closed")
    _post_zero(client, cid)
    model = {
        "procurement_law": "44fz",
        "procurement_number": "0348100024426000039",
        "application_deadline": "2026-10-23T10:00:00+03:00",
        "deadline_status": "expired",
        "field_evidence": {"application_deadline": "eis_notice:0348100024426000039/endDT"},
    }
    resp = _decision(client, cid, _request(procurement_model=model))
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision_core"]["decision"]["status"] == "NO_GO"
    assert resp.json()["competitive_recommendation"] == "NO_GO"
    assert resp.json()["assessment"]["eligibility_status"] == "NOT_ASSESSED"
