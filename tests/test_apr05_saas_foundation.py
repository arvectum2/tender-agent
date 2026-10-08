"""APR-05 tenant isolation, invitation lifecycle, legal and monthly entitlement checks."""
from __future__ import annotations

import base64
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.modules.customer_onboarding import router as onboarding
from src.modules.saas_foundation import router as saas
from src.modules.saas_foundation import service
from src.modules.saas_foundation.models import (
    SaasAccessToken,
    SaasInvitation,
    SaasLegalAcceptance,
    SaasPaymentEvidence,
    SaasTenant,
    SaasUsageCounter,
)
from src.shared.config.settings import Settings


@pytest.fixture(autouse=True)
def enabled(monkeypatch, tmp_path):
    s = Settings(
        _env_file=None,
        saas_foundation_enabled=True,
        pilot_auth_enabled=True,
        pilot_auth_username="operator",
        pilot_auth_password="unit-test-only-operator-password-of-safe-length-2026",
    )
    monkeypatch.setattr(saas, "get_settings", lambda: s)
    monkeypatch.setattr(onboarding, "get_settings", lambda: SimpleNamespace(arvectum_data_dir=str(tmp_path)))


def _operator(client):
    encoded = base64.b64encode(b"operator:unit-test-only-operator-password-of-safe-length-2026").decode()
    return {"Authorization": "Basic " + encoded}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _new_customer(client, name):
    response = client.post("/customers", json={"legal_name": name, "customer_status": "PROSPECT"})
    assert response.status_code == 201, response.text
    return response.json()["customer_id"]


def _seed(client, name):
    customer_id = _new_customer(client, name)
    res = client.post("/api/operator/saas/tenants", json={"customer_id": customer_id}, headers=_operator(client))
    assert res.status_code == 201, res.text
    tenant = res.json()
    r = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": tenant["invitation"]["invitation_code"], "display_name": name + " owner",
    })
    assert r.status_code == 201, r.text
    cred = r.json()
    assert cred["role"] == "owner"
    return tenant, cred["access_token"]


def _legal(client, token):
    policy = client.get("/api/saas/legal", headers=_auth(token))
    assert policy.status_code == 200, policy.text
    info = policy.json()
    accepted = client.post("/api/saas/legal/accept", headers=_auth(token), json={
        "terms_version": info["terms_version"], "privacy_version": info["privacy_version"],
        "confirm_read": True,
    })
    assert accepted.status_code == 200, accepted.text


def _profile():
    return {
        "criteria": {
            "categories": ["ИТ"], "regions": ["Москва"], "keywords": ["разработка"],
            "price_min": 100000, "price_max": 900000,
        },
        "commercial": {"target_margin_percent": 20},
        "qualification": {"licenses": ["Не проверенная лицензия"], "sro_approvals": []},
        "risk_preferences": {"tolerance": "low"},
    }


def test_operator_bootstrap_requires_basic_not_tenant_token(client):
    customer = _new_customer(client, "ООО Проверка оператора")
    endpoint = "/api/operator/saas/tenants"
    assert client.post(endpoint, json={"customer_id": customer}).status_code == 401
    assert client.post(endpoint, json={"customer_id": customer}, headers=_auth("saas_wrong")).status_code == 401
    ok = client.post(endpoint, json={"customer_id": customer}, headers=_operator(client))
    assert ok.status_code == 201
    assert ok.json()["payment_collected"] is False
    assert client.post(endpoint, json={"customer_id": customer}, headers=_operator(client)).status_code == 409
    assert client.get("/api/saas/packages").json()["online_checkout_enabled"] is False


def test_invitation_secret_hash_only_single_use_and_role(client, session):
    tenant, token = _seed(client, "ООО Приглашения")
    hashed = list(session.scalars(select(SaasAccessToken)))
    assert len(hashed) == 1
    assert hashed[0].token_sha256 == service.digest(token)
    assert token not in str(hashed[0].__dict__)
    response = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": tenant["invitation"]["invitation_code"], "display_name": "Replay",
    })
    assert response.status_code == 410
    assert client.get("/api/saas/me").status_code == 401
    assert client.get("/api/saas/me", headers=_operator(client)).status_code == 401


def test_legal_gate_is_per_member_and_requires_current_versions(client, session):
    tenant, owner = _seed(client, "ООО Юридический контроль")
    response = client.put("/api/saas/profile", json=_profile(), headers=_auth(owner))
    assert response.status_code == 428
    policy = client.get("/api/saas/legal", headers=_auth(owner)).json()
    bad = client.post("/api/saas/legal/accept", headers=_auth(owner), json={
        "terms_version": "not-current", "privacy_version": policy["privacy_version"], "confirm_read": True,
    })
    assert bad.status_code == 409
    _legal(client, owner)
    assert client.put("/api/saas/profile", json=_profile(), headers=_auth(owner)).status_code == 200
    assert session.scalar(select(SaasLegalAcceptance).where(
        SaasLegalAcceptance.tenant_id == tenant["tenant_id"]
    )) is not None


def test_tenant_profiles_are_scoped_and_roles_enforced(client):
    a, ta = _seed(client, "ООО Изоляция А")
    b, tb = _seed(client, "ООО Изоляция Б")
    _legal(client, ta)
    _legal(client, tb)
    assert client.put("/api/saas/profile", headers=_auth(ta), json=_profile()).status_code == 200
    response = client.get("/api/saas/profile", headers=_auth(tb))
    assert response.status_code == 200
    assert response.json()["customer_id"] == b["customer_id"]
    assert response.json()["profile"] is None
    own = client.get("/api/saas/profile", headers=_auth(ta))
    assert own.json()["customer_id"] == a["customer_id"]
    assert own.json()["profile"]["criteria"]["price_max"] == 900000
    issued = client.post("/api/saas/invitations", headers=_auth(ta), json={
        "role": "viewer", "acquisition_channel": "referral",
    })
    assert issued.status_code == 200, issued.text
    viewer = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": issued.json()["invitation_code"], "display_name": "Наблюдатель",
    }).json()["access_token"]
    assert client.get("/api/saas/profile", headers=_auth(viewer)).status_code == 428
    _legal(client, viewer)
    assert client.get("/api/saas/profile", headers=_auth(viewer)).status_code == 200
    assert client.put("/api/saas/profile", headers=_auth(viewer), json=_profile()).status_code == 403
    assert client.post("/api/saas/invitations", headers=_auth(viewer), json={"role": "admin"}).status_code == 403
    assert client.get("/api/saas/members", headers=_auth(tb)).json()["members"][0]["role"] == "owner"


def test_member_revoke_and_logout_fail_closed(client):
    _tenant, owner = _seed(client, "ООО Отзыв доступа")
    _legal(client, owner)
    issued = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": "analyst"}).json()
    user = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": issued["invitation_code"], "display_name": "Аналитик",
    }).json()
    assert client.get("/api/saas/me", headers=_auth(user["access_token"])).status_code == 200
    assert client.post(f"/api/saas/members/{user['member_id']}/revoke", headers=_auth(owner)).status_code == 200
    assert client.get("/api/saas/me", headers=_auth(user["access_token"])).status_code == 401
    self_revoke = client.post(f"/api/saas/members/{user['member_id']}/revoke", headers=_auth(owner))
    assert self_revoke.status_code == 200
    assert client.post("/api/saas/logout", headers=_auth(owner)).status_code == 200
    assert client.get("/api/saas/me", headers=_auth(owner)).status_code == 401


def test_quota_meters_actual_screens_and_refunds_on_failure(client, session, monkeypatch):
    tenant, owner = _seed(client, "ООО Метрики")
    _legal(client, owner)
    client.put("/api/saas/profile", headers=_auth(owner), json=_profile())
    monkeypatch.setattr(onboarding, "preanalysis_from_public_search",
                        lambda reference: {
                            "source_status": "success_with_results", "initial_price": {
                                "status": "KNOWN", "value": 450000, "citations": [
                                    {"source_ref": "public:card", "document": "ЕИС", "locator": "page:1"}
                                ]
                            }
                        })
    for _ in range(service.PACKAGES["pilot"]["quota"]["screens"]):
        res = client.post("/api/saas/screen", headers=_auth(owner), json={"reference": "0123456789026000001"})
        assert res.status_code == 200, res.text
        assert res.json()["decision"] == "HUMAN_REVIEW_REQUIRED"
    used = client.get("/api/saas/usage", headers=_auth(owner)).json()["metrics"]["screens"]
    assert used["used"] == used["limit"] == 30 and used["remaining"] == 0
    assert client.post("/api/saas/screen", headers=_auth(owner),
                       json={"reference": "0123456789026000001"}).status_code == 429
    row = session.scalar(select(SaasUsageCounter).where(
        SaasUsageCounter.tenant_id == tenant["tenant_id"],
        SaasUsageCounter.metric == "screens",
    ))
    assert row.used == 30


def test_failed_file_upload_refunds_quota(client, session):
    _tenant, owner = _seed(client, "ООО Лимиты документов")
    _legal(client, owner)
    failed = client.post("/api/saas/documents", headers=_auth(owner),
                         data={"document_key": "bad_doc", "document_type": "LICENSE", "display_name": "Ошибка"},
                         files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert failed.status_code == 415
    metrics = client.get("/api/saas/usage", headers=_auth(owner)).json()["metrics"]
    assert metrics["documents"]["used"] == 0


def test_owned_run_prevents_cross_tenant_access(client, monkeypatch, tmp_path):
    from src.modules.tender_operator_agent_demo import upload_service_legacy as uploads

    monkeypatch.setattr(uploads, "DEMO_RUNS_ROOT", tmp_path / "runs", raising=False)
    a, first = _seed(client, "ООО Тендер А")
    b, second = _seed(client, "ООО Тендер Б")
    _legal(client, first)
    _legal(client, second)
    files = [("files", ("notice.txt", b"Notice for synthetic procurement", "text/plain"))]
    own = client.post("/api/saas/runs", headers=_auth(first),
                      data={"tender_title": "Синтетическая закупка", "tender_category": "ИТ"}, files=files)
    assert own.status_code == 201, own.text
    run_id = own.json()["run_id"]
    assert own.json()["tenant_id"] == a["tenant_id"]
    for suffix, method in [("/report", "get"), ("/analyze", "post"), ("/screen", "post")]:
        method_func = getattr(client, method)
        other = method_func(f"/api/saas/runs/{run_id}{suffix}", headers=_auth(second))
        assert other.status_code == 404, other.text
    assert client.get("/api/saas/usage", headers=_auth(second)).json()["metrics"]["runs"]["used"] == 0
    assert client.get("/api/saas/usage", headers=_auth(first)).json()["metrics"]["runs"]["used"] == 1
    assert b["tenant_id"] != a["tenant_id"]


def test_trial_expiration_suspension_and_manual_payment_checks(client, session):
    tenant, owner = _seed(client, "ООО Оплата")
    row = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant["tenant_id"]))
    row.trial_ends_at = service.now_utc() - timedelta(seconds=2)
    session.commit()
    assert client.get("/api/saas/me", headers=_auth(owner)).status_code == 402
    assert client.post("/api/operator/saas/tenants/" + tenant["tenant_id"] + "/verify-manual-payment",
                       json={"external_reference": "bad", "operator_note": "x",
                             "personally_verified_against_external_statement": True},
                       headers=_operator(client)).status_code == 422
    paid = client.post("/api/operator/saas/tenants/" + tenant["tenant_id"] + "/verify-manual-payment",
                       json={"external_reference": "TEST-EXT-REF-0001",
                             "operator_note": "Синтетическая отметка: оплата не проводилась",
                             "personally_verified_against_external_statement": True},
                       headers=_operator(client))
    assert paid.status_code == 200, paid.text
    assert paid.json()["payment_provider_called"] is False
    assert client.get("/api/saas/me", headers=_auth(owner)).status_code == 200
    assert session.scalar(select(SaasPaymentEvidence)).external_reference == "TEST-EXT-REF-0001"
    suspended = client.post(f"/api/operator/saas/tenants/{tenant['tenant_id']}/suspend", headers=_operator(client))
    assert suspended.status_code == 200
    assert client.get("/api/saas/me", headers=_auth(owner)).status_code == 403


def test_disabled_default_and_public_ui_headers(client, monkeypatch):
    response = client.get("/saas")
    assert response.status_code == 200
    assert "Токен показывается только один раз" in response.text
    assert "localStorage" not in response.text
    assert client.get("/api/saas/packages").status_code == 200
    disabled = Settings(_env_file=None, saas_foundation_enabled=False)
    monkeypatch.setattr(saas, "get_settings", lambda: disabled)
    assert client.get("/api/saas/packages").status_code == 404
    assert client.get("/saas").status_code == 404


def test_role_seats_are_enforced_before_issuing_invites(client):
    tenant, owner = _seed(client, "ООО Лимит рабочих мест")
    _legal(client, owner)
    for who in ("admin", "viewer"):
        created = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": who})
        assert created.status_code == 200, created.text
    additional = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": "analyst"})
    assert additional.status_code == 429
    assert client.get("/api/operator/saas/tenants/" + tenant["tenant_id"],
                      headers=_operator(client)).json()["plan_code"] == "pilot"


def test_tenant_token_rotation_and_malformed_operator_auth(client):
    _tenant, token = _seed(client, "ООО Замена ключа")
    rotated = client.post("/api/saas/token/rotate", headers=_auth(token))
    assert rotated.status_code == 200, rotated.text
    next_token = rotated.json()["access_token"]
    assert next_token != token
    assert client.get("/api/saas/me", headers=_auth(token)).status_code == 401
    assert client.get("/api/saas/me", headers=_auth(next_token)).status_code == 200
    assert client.post("/api/operator/saas/tenants",
                       headers={"Authorization": "Basic !invalid!"},
                       json={"customer_id": "CUS-none"}).status_code == 401


def test_customer_document_download_cannot_cross_tenant(client):
    _ta, a = _seed(client, "ООО Документы арендатора А")
    _tb, b = _seed(client, "ООО Документы арендатора Б")
    _legal(client, a)
    _legal(client, b)
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"
    path = "/api/saas/documents"
    doc = client.post(path, headers=_auth(a), data={
        "document_key": "private_license", "document_type": "LICENSE",
        "display_name": "Private test license",
    }, files={"file": ("private.pdf", pdf, "application/pdf")})
    assert doc.status_code == 201, doc.text
    own = client.get(path + "/private_license/download", headers=_auth(a))
    assert own.status_code == 200 and own.content == pdf
    forbidden = client.get(path + "/private_license/download", headers=_auth(b))
    assert forbidden.status_code == 404
    assert client.get("/api/saas/usage", headers=_auth(b)).json()["metrics"]["documents"]["used"] == 0


def test_oversized_tender_upload_is_bounded_and_refunded(client):
    _tenant, owner = _seed(client, "ООО Защита памяти")
    _legal(client, owner)
    too_large = b"a" * (12 * 1024 * 1024 + 1)
    res = client.post("/api/saas/runs", headers=_auth(owner),
                      data={"tender_title": "Oversized test"},
                      files={"files": ("large.txt", too_large, "text/plain")})
    assert res.status_code == 413, res.text
    usage = client.get("/api/saas/usage", headers=_auth(owner)).json()["metrics"]
    assert usage["runs"]["used"] == 0


def test_invitation_expiry_and_sensitive_secret_is_never_audit_detail(client, session):
    tenant, owner = _seed(client, "ООО Приглашение на срок")
    _legal(client, owner)
    invite = client.post("/api/saas/invitations", headers=_auth(owner),
                         json={"role": "viewer"}).json()
    row = session.scalar(select(SaasInvitation).where(
        SaasInvitation.token_sha256 == service.digest(invite["invitation_code"])))
    row.expires_at = service.now_utc() - timedelta(seconds=1)
    session.commit()
    assert client.post("/api/saas/invitations/redeem", json={
        "invitation_code": invite["invitation_code"], "display_name": "Сотрудник"
    }).status_code == 410
    from src.modules.saas_foundation.models import SaasAuditEvent
    audit = [r.detail for r in session.scalars(select(SaasAuditEvent).where(
        SaasAuditEvent.tenant_id == tenant["tenant_id"]))]
    assert all(owner not in item and invite["invitation_code"] not in item for item in audit)


def test_eis_readonly_import_is_tenant_bound_and_metered(client, monkeypatch):
    from types import SimpleNamespace

    from src.modules.saas_foundation import router as saas_router

    _a, a = _seed(client, "ООО SOAP Контур А")
    _b, b = _seed(client, "ООО SOAP Контур Б")
    _legal(client, a)
    _legal(client, b)
    seen = []

    def fake_eis(request):
        seen.append((request.reestr_number, request.download_archive,
                     request.analyze_after_download))
        return SimpleNamespace(
            run_id="toa-run-synthetic-eis-apr05",
            status="ready_to_analyze",
            downloaded_files_count=3,
        )

    monkeypatch.setattr(saas_router, "create_run_from_eis_docs_archive", fake_eis)
    bad = client.post("/api/saas/runs/from-eis", headers=_auth(a),
                      json={"reference": "https://evil.example/eis?regNumber=0123456789026000001"})
    assert bad.status_code == 422
    assert client.get("/api/saas/usage", headers=_auth(a)).json()["metrics"]["runs"]["used"] == 0
    r = client.post("/api/saas/runs/from-eis", headers=_auth(a),
                    json={"reference": "0123456789026000001"})
    assert r.status_code == 201, r.text
    assert r.json()["external_action_allowed"] is False
    assert seen == [("0123456789026000001", True, False)]
    assert client.get("/api/saas/usage", headers=_auth(a)).json()["metrics"]["runs"]["used"] == 1
    assert client.get("/api/saas/usage", headers=_auth(b)).json()["metrics"]["runs"]["used"] == 0
    assert client.post("/api/saas/runs/toa-run-synthetic-eis-apr05/screen",
                       headers=_auth(b)).status_code == 404


def test_paid_pilot_no_live_checkout_and_tenant_metrics_scoped(client):
    _a, a = _seed(client, "ООО Метрики отдельно А")
    _b, b = _seed(client, "ООО Метрики отдельно Б")
    _legal(client, a)
    _legal(client, b)
    packages = client.get("/api/saas/packages").json()
    assert packages["payment_provider_connected"] is False
    assert packages["public_offer_published"] is False
    assert packages["packages"]["pilot"]["seats"] == 3
    assert packages["packages"]["team"]["seats"] == 15
    metr_a = client.get("/api/saas/metrics", headers=_auth(a)).json()
    metr_b = client.get("/api/saas/metrics", headers=_auth(b)).json()
    assert metr_a["tenant_id"] != metr_b["tenant_id"]
    assert metr_a["product_metrics"]["owned_tender_runs"] == 0
    assert metr_b["product_metrics"]["owned_tender_runs"] == 0
    assert metr_a["external_action_allowed"] is False
