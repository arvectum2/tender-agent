"""APR05 actual-company identity / synthetic tenant gate on a COPY of APR04's DB.

Never accepts terms for the real owner, records payment, sends invitations,
starts a public service or uses real credentials.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from pathlib import Path
from secrets import token_urlsafe


def main() -> int:
    root = Path("/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr05-staged-isolation-20261015")
    apr04 = Path("/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr04-owner-onboarding-20261015")
    assert root.name == "ta-apr05-staged-isolation-20261015"
    receipt = json.loads((apr04 / "output/apr04_owner_onboarding_e2e_receipt.json").read_text())
    customer_id = receipt["company_id"]
    assert receipt["database_session_reopen"] is True
    root.mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(exist_ok=True)
    stage = root / "staging-only-saas.sqlite"
    if stage.exists():
        raise RuntimeError("Isolated APR05 tenant test already exists. Do not reuse token/paid state.")
    shutil.copy2(apr04 / "apr04-isolated.sqlite", stage)
    original_hash = hashlib.sha256(stage.read_bytes()).hexdigest()
    os.chmod(stage, 0o600)
    operator_password = token_urlsafe(40)
    os.environ.update({
        "AI_CORP_DATABASE_URL": "sqlite:///" + str(stage),
        "AI_CORP_ARVECTUM_DATA_DIR": str(root / "data"),
        "AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR": str(apr04 / "runs"),
        "AI_CORP_SAAS_FOUNDATION_ENABLED": "true",
        "AI_CORP_PILOT_AUTH_ENABLED": "true",
        "AI_CORP_PILOT_AUTH_USERNAME": "isolated-apr05-operator",
        "AI_CORP_PILOT_AUTH_PASSWORD": operator_password,
        "AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES": "/api/operator,/pilot",
    })
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from src.modules.saas_foundation import router as saas
    from src.modules.saas_foundation.models import (
        SaasAccessToken,
        SaasLegalAcceptance,
        SaasPaymentEvidence,
        SaasTenant,
    )
    from src.shared.api.dependencies import get_db_session
    from src.shared.api.errors import register_exception_handlers
    from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
    from src.shared.config.settings import get_settings
    from src.shared.db import models as _models  # noqa: F401

    get_settings.cache_clear()
    assert get_settings().saas_foundation_enabled
    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(saas.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware, username="isolated-apr05-operator",
        password=operator_password, protected=("/api/operator",),
        public=("/health",), tenant_api_enabled=True,
    )
    def session_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db_session] = session_override
    basic = {"Authorization": "Basic " + base64.b64encode(
        ("isolated-apr05-operator:" + operator_password).encode()
    ).decode()}
    results: dict[str, object] = {"copied_seed_sha256": original_hash}
    with TestClient(app) as client:
        prices = client.get("/api/saas/packages")
        results["packages_http"] = prices.status_code
        assert prices.status_code == 200
        details = prices.json()
        assert details["online_checkout_enabled"] is False
        assert details["payment_provider_connected"] is False
        assert details["public_offer_published"] is False
        results["online_checkout_enabled"] = False

        blocked = client.post("/api/operator/saas/tenants", json={
            "customer_id": customer_id, "plan_code": "pilot",
        })
        results["anonymous_operator_denied"] = blocked.status_code
        assert blocked.status_code == 401
        created = client.post("/api/operator/saas/tenants", headers=basic, json={
            "customer_id": customer_id, "plan_code": "pilot",
        })
        results["tenant_created"] = created.status_code
        assert created.status_code == 201, created.text[:180]
        tenant = created.json()
        assert tenant["billing_state"] == "trial"
        assert tenant["payment_collected"] is False
        results["tenant_matches_real_company_id"] = tenant["customer_id"] == customer_id
        results["tenant_trial_is_synthetic_only"] = True
        assert results["tenant_matches_real_company_id"]
        repeat = client.post("/api/operator/saas/tenants", headers=basic, json={
            "customer_id": customer_id, "plan_code": "pilot",
        })
        results["duplicate_tenant_denied"] = repeat.status_code
        assert repeat.status_code == 409

        redeem = client.post("/api/saas/invitations/redeem", json={
            "invitation_code": tenant["invitation"]["invitation_code"],
            "display_name": "APR05 synthetic test identity, not corporate signatory",
        })
        results["invite_redeemed"] = redeem.status_code
        assert redeem.status_code == 201, redeem.text[:200]
        test_access_token = redeem.json()["access_token"]
        assert redeem.json()["role"] == "owner"
        headers = {"Authorization": "Bearer " + test_access_token}
        replay = client.post("/api/saas/invitations/redeem", json={
            "invitation_code": tenant["invitation"]["invitation_code"],
            "display_name": "APR05 synthetic duplicate",
        })
        results["reused_invitation_denied"] = replay.status_code
        assert replay.status_code == 410

        member = client.get("/api/saas/me", headers=headers)
        results["test_member_session"] = member.status_code
        assert member.status_code == 200
        before_consent = client.get("/api/saas/profile", headers=headers)
        results["profile_without_owner_legal_consent"] = before_consent.status_code
        assert before_consent.status_code == 428
        legal = client.get("/api/saas/legal", headers=headers)
        results["legal_document_read_only"] = legal.status_code
        assert legal.status_code == 200
        # No /legal/accept or verify-payment operation is ever performed.
        denied_change = client.put("/api/saas/profile", headers=headers, json={
            "criteria": {"categories": ["synthetic-test-only"]},
        })
        results["change_without_consent_denied"] = denied_change.status_code
        assert denied_change.status_code == 428

        logout = client.post("/api/saas/logout", headers=headers)
        results["test_token_revoked"] = logout.status_code == 200
        assert results["test_token_revoked"]
        revoked = client.get("/api/saas/me", headers=headers)
        results["revoked_access_denied"] = revoked.status_code
        assert revoked.status_code == 401

    with Session(engine) as session:
        tenant_db = session.scalar(select(SaasTenant).where(
            SaasTenant.customer_id == customer_id
        ))
        assert tenant_db is not None
        assert tenant_db.billing_state == "trial"
        assert session.scalar(select(SaasLegalAcceptance).where(
            SaasLegalAcceptance.tenant_id == tenant_db.tenant_id
        )) is None
        assert session.scalars(select(SaasPaymentEvidence).where(
            SaasPaymentEvidence.tenant_id == tenant_db.tenant_id
        )).first() is None
        tokens = session.scalars(select(SaasAccessToken).where(
            SaasAccessToken.tenant_id == tenant_db.tenant_id
        )).all()
        assert all(test_access_token != tok.token_sha256 for tok in tokens)
        results["payment_evidence_count"] = 0
        results["company_legal_acceptance_count"] = 0
        results["raw_token_persisted"] = False
    # This stage must never have changed the APR04 source database.
    assert hashlib.sha256((apr04 / "apr04-isolated.sqlite").read_bytes()).hexdigest() == original_hash
    results.update({
        "source_type": "isolated_copy_of_apr04_verified_identity_db",
        "original_apr04_database_mutated": False,
        "no_real_subscription_or_company_consent": True,
        "no_prod_or_external_communications": True,
        "no_etp_actions": True,
        "pending": "Owner legal consent, approved terms, payment provider and production."
    })
    file = root / "output/apr05_owner_tenant_gate_receipt.json"
    file.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print("APR05_TEST_TENANT_GATE", json.dumps({
        k: results[k] for k in (
            "packages_http","tenant_created","anonymous_operator_denied",
            "duplicate_tenant_denied","invite_redeemed","reused_invitation_denied",
            "profile_without_owner_legal_consent","change_without_consent_denied",
            "revoked_access_denied","payment_evidence_count",
            "company_legal_acceptance_count",
        )
    }, ensure_ascii=False))
    print("PRIVATE_RECEIPT", file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
