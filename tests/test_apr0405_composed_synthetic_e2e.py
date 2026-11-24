"""APR03B/04/05 synthetic API composition: no real source, LLM, payment or ETP."""
import base64
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from src.modules.customer_onboarding import router as onboarding
from src.modules.deal_registry.models import Deal
from src.modules.saas_foundation import router as saas
from src.modules.saas_foundation.models import (
    CompanyPortfolioDecision,
    SaasLegalAcceptance,
    SaasPaymentEvidence,
)
from src.modules.saas_foundation.service import now_utc
from src.shared.config.settings import Settings

REGISTRY = "0123456789012345678"
BASIC = "Basic " + base64.b64encode(
    b"operator:synthetic-unit-test-operator-password-2026-only"
).decode()


@pytest.fixture(autouse=True)
def synthetic_config(monkeypatch, tmp_path):
    settings = Settings(
        _env_file=None, saas_foundation_enabled=True,
        pilot_auth_enabled=True, pilot_auth_username="operator",
        pilot_auth_password="synthetic-unit-test-operator-password-2026-only",
        arvectum_data_dir=str(tmp_path),
    )
    monkeypatch.setattr(saas, "get_settings", lambda: settings)
    monkeypatch.setattr(onboarding, "get_settings", lambda: settings)
    monkeypatch.setattr(
        onboarding, "preanalysis_from_public_search",
        lambda reference: {
            "contract_version": "fast-cited-preanalysis-v1",
            "initial_price": {
                "status": "KNOWN", "value": 400000,
                "citations": [{"source_ref": "synthetic:case-1",
                               "document": "SYNTHETIC NOT OFFICIAL",
                               "locator": "fixture:line:1"}],
            },
            "subject": {"status": "UNKNOWN", "value": None, "citations": []},
            "decision": "HUMAN_REVIEW_REQUIRED",
            "external_action_allowed": False,
        },
    )


def auth(token):
    return {"Authorization": "Bearer " + token}


def company(client, name):
    response = client.post("/api/onboarding/customers", headers={"Authorization": BASIC}, json={
        "legal_name": name,
        "criteria": {"categories": ["ИТ"], "regions": ["Москва"],
                     "keywords": ["синтетический"], "price_min": None, "price_max": None},
        "commercial": {}, "qualification": {"licenses": [], "sro_approvals": []},
        "risk_preferences": {"tolerance": "low"},
    })
    assert response.status_code == 201, response.text
    assert response.json()["documents_verified"] is False
    return response.json()["customer_id"]


def tenant(client, customer_id):
    created = client.post("/api/operator/saas/tenants",
                          json={"customer_id": customer_id},
                          headers={"Authorization": BASIC})
    assert created.status_code == 201, created.text
    invitation = created.json()["invitation"]["invitation_code"]
    redeemed = client.post("/api/saas/invitations/redeem",
                           json={"invitation_code": invitation,
                                 "display_name": "Synthetic owner"})
    assert redeemed.status_code == 201, redeemed.text
    return redeemed.json()["access_token"]


def accept_synthetic_legal(client, token):
    policy = client.get("/api/saas/legal", headers=auth(token))
    assert policy.status_code == 200
    response = client.post("/api/saas/legal/accept", headers=auth(token), json={
        "terms_version": policy.json()["terms_version"],
        "privacy_version": policy.json()["privacy_version"], "confirm_read": True,
    })
    assert response.status_code == 200, response.text


def test_composed_source_unknown_legal_hold_two_tenants_and_defer(client, session):
    ids = [company(client, f"ООО SYNTHETIC APR {n}") for n in ("A", "B")]
    for customer_id in ids:
        response = client.post(f"/api/onboarding/customers/{customer_id}/screen",
                               headers={"Authorization": BASIC},
                               json={"reference": REGISTRY})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["profile_checks"]["nmck"]["status"] == "UNKNOWN"
        assert data["profile_checks"]["nmck"]["citations"][0]["source_ref"] == "synthetic:case-1"
        assert data["decision"] == "HUMAN_REVIEW_REQUIRED"
        assert data["external_action_allowed"] is False
    a, b = (tenant(client, customer_id) for customer_id in ids)
    cases = "/api/saas/company-portfolio/cases"
    payload = {"registry_number": REGISTRY}
    assert client.post(cases, headers=auth(a), json=payload).status_code == 428
    assert client.post(cases, headers=auth(b), json=payload).status_code == 428
    assert session.scalar(select(func.count(SaasLegalAcceptance.id))) == 0
    accept_synthetic_legal(client, a)
    assert client.post(cases, headers=auth(b), json=payload).status_code == 428
    created_a = client.post(cases, headers=auth(a), json=payload)
    assert created_a.status_code == 201, created_a.text
    accept_synthetic_legal(client, b)
    created_b = client.post(cases, headers=auth(b), json=payload)
    assert created_b.status_code == 201, created_b.text
    ca, cb = created_a.json(), created_b.json()
    assert ca["case_id"] != cb["case_id"]
    assert not ca["source_verified"] and not cb["source_verified"]
    assert not ca["external_submission_allowed"] and not cb["external_submission_allowed"]
    path = cases + "/" + ca["case_id"]
    assert client.get(path, headers=auth(b)).status_code == 404
    assert client.get(path + "/decisions", headers=auth(b)).status_code == 404
    cross_write = client.post(path + "/decisions", headers=auth(b), json={
        "action": "GO", "rationale": "SYNTHETIC unauthorized foreign tenant",
        "expected_revision": 0, "idempotency_key": "synthetic-foreign-denied-1",
    })
    assert cross_write.status_code == 404
    deferred = client.post(path + "/decisions", headers=auth(a), json={
        "action": "DEFER", "rationale": "SYNTHETIC: originals remain unverified",
        "deferred_until": (now_utc() + timedelta(days=2)).isoformat(),
        "expected_revision": 0, "idempotency_key": "synthetic-apr0405-defer-001",
    })
    assert deferred.status_code == 200, deferred.text
    assert deferred.json()["action"] == "DEFER"
    pa = client.get(cases, headers=auth(a)).json()
    pb = client.get(cases, headers=auth(b)).json()
    assert pa["customer_id"] == ids[0] and pb["customer_id"] == ids[1]
    assert [v["decision"]["action"] for v in pa["items"]] == ["DEFER"]
    assert [v["decision"] for v in pb["items"]] == [None]
    assert not pa["external_submission_allowed"] and not pb["external_submission_allowed"]
    assert session.scalar(select(func.count(SaasLegalAcceptance.id))) == 2
    assert session.scalar(select(func.count(SaasPaymentEvidence.id))) == 0
    assert session.scalar(select(func.count(CompanyPortfolioDecision.id))) == 1
    assert session.scalar(select(func.count(Deal.id))) == 0
