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


def test_supplier_legal_name_never_becomes_procurement_customer(client, monkeypatch):
    from types import SimpleNamespace

    _tenant, owner = _seed(client, "ООО Поставщик не Заказчик")
    _legal(client, owner)
    observed = {}

    def synthetic_run(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(run_id="toa-run-apr05-correct-customer-role",
                               status="ready_to_analyze")

    monkeypatch.setattr(saas, "create_uploaded_demo_run", synthetic_run)
    response = client.post(
        "/api/saas/runs", headers=_auth(owner),
        data={"tender_title": "Синтетическая разработка сайта"},
        files={"files": ("notice.txt", b"notice", "text/plain")},
    )
    assert response.status_code == 201, response.text
    assert observed["customer_name"] == "Не установлен (требует проверки)"
    assert observed["customer_name"] != "ООО Поставщик не Заказчик"
    assert "unverified" in observed["notes"]



def test_operator_and_tenant_ui_cover_invite_workflows_without_public_auth(client):
    from src.modules.customer_onboarding.ui import render_onboarding_html
    from src.modules.saas_foundation.ui import render_saas_html

    operator = render_onboarding_html()
    customer = render_saas_html()
    assert 'id="saas-bootstrap"' in operator
    assert '/api/operator/saas/tenants' in operator
    assert 'id="saas-selected-plan"' in operator
    assert 'id="invite-member"' in customer
    assert 'id="members-list"' in customer
    assert 'id="revoke-member"' in customer
    assert 'localStorage' not in customer
    assert 'sessionStorage' not in customer


def test_saas_qualification_uses_signed_tenant_identity_and_zero_references(client):
    import json
    from pathlib import Path

    case = json.loads((
        Path(__file__).resolve().parents[1]
        / "docs/acceptance/arvectum_owner_reference_list_and_czn_2026-10-13.json"
    ).read_text(encoding="utf-8"))
    a, owner_a = _seed(client, "ООО Саас Квалификация А")
    b, owner_b = _seed(client, "ООО Саас Квалификация Б")
    base = "/api/saas/qualification"
    criterion = case["czn_source_bound_criterion"]

    # No inferred customer and no unauthenticated reads.
    assert client.post(f"{base}/assess", json=criterion).status_code == 401
    assert client.post(f"{base}/assess", headers=_auth(owner_a), json=criterion).status_code == 428
    _legal(client, owner_a)
    _legal(client, owner_b)
    missing = client.get(f"{base}/references", headers=_auth(owner_a))
    assert missing.status_code == 200
    assert missing.json()["state"] == "UNKNOWN"

    saved = client.post(
        f"{base}/references", headers=_auth(owner_a),
        json={
            "snapshot": case["reference_fact_value"],
            "source_ref": case["reference_fact_source_ref"],
            "expected_version": 0,
        },
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["customer_id"] == a["customer_id"]
    assert saved.json()["fact_version"] == 1
    assert saved.json()["external_action_allowed"] is False

    result = client.post(f"{base}/assess", headers=_auth(owner_a), json=criterion)
    assert result.status_code == 200, result.text
    assert result.json()["customer_id"] == a["customer_id"]
    assert result.json()["recommendation"] == "NO_GO_QUALIFICATION_COMPETITIVENESS"
    assert result.json()["qualifying_contracts"] == 0

    # Different tenant is not affected by first tenant's confirmed zero.
    other = client.post(f"{base}/assess", headers=_auth(owner_b), json=criterion)
    assert other.status_code == 200, other.text
    assert other.json()["customer_id"] == b["customer_id"]
    assert other.json()["recommendation"] == "QUALIFICATION_EVIDENCE_UNKNOWN"
    assert client.get(f"{base}/references", headers=_auth(owner_b)).json()["state"] == "UNKNOWN"

    core_payload = {
        "criterion": criterion,
        "source_binding": {
            "procurement_number": criterion["procurement_number"],
            "notice_version": criterion["procurement_notice_version"],
            "document_uid": criterion["source_document_uid"],
            "document_sha256": criterion["source_document_sha256"],
            "application_deadline_date": criterion["application_deadline_date"],
        },
        "procurement_model": {
            "procurement_number": criterion["procurement_number"],
            "procurement_law": "44fz",
        },
    }
    core = client.post(f"{base}/decision-core", headers=_auth(owner_a), json=core_payload)
    assert core.status_code == 200, core.text
    assert core.json()["competitive_recommendation"] == "NO_GO"
    assert core.json()["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert core.json()["external_action_allowed"] is False


def test_saas_qualification_viewer_cannot_write_reference_list(client):
    import json
    from pathlib import Path

    case = json.loads((
        Path(__file__).resolve().parents[1]
        / "docs/acceptance/arvectum_owner_reference_list_and_czn_2026-10-13.json"
    ).read_text(encoding="utf-8"))
    _tenant, owner = _seed(client, "ООО Чтение референсов")
    _legal(client, owner)
    invite = client.post(
        "/api/saas/invitations", headers=_auth(owner),
        json={"role": "viewer", "acquisition_channel": "referral"},
    ).json()
    viewer = client.post(
        "/api/saas/invitations/redeem",
        json={"invitation_code": invite["invitation_code"], "display_name": "Viewer"},
    ).json()["access_token"]
    _legal(client, viewer)
    result = client.post(
        "/api/saas/qualification/references",
        headers=_auth(viewer),
        json={
            "snapshot": case["reference_fact_value"],
            "source_ref": case["reference_fact_source_ref"],
            "expected_version": 0,
        },
    )
    assert result.status_code == 403
    denied = client.get("/api/saas/qualification/references", headers=_auth(viewer))
    assert denied.status_code == 403


def test_saas_auto_qualification_only_for_owned_run_without_request_scores(
    client, monkeypatch,
):
    from types import SimpleNamespace

    from src.modules.saas_foundation import router as saas

    tenant_a, token_a = _seed(client, "ООО Авторизованный EIS")
    _, token_b = _seed(client, "ООО Другая компания")
    _legal(client, token_a)
    _legal(client, token_b)
    upload = client.post(
        "/api/saas/runs",
        headers=_auth(token_a),
        data={
            "tender_title": "Тестовый конкурc",
            "procurement_customer_name": "Публичный заказчик",
        },
        files=[("files", ("contract.txt", b"test tender reference", "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    run_id = upload.json()["run_id"]
    observed = []

    def fake_qualification(session, *, run_id, customer_id, as_of):
        observed.append((run_id, customer_id))
        return {
            "source_status": "ORIGINAL_EIS_TRANSPORT_CORRELATED_SIGNATURE_NOT_VERIFIED",
            "competitive_recommendation": "NO_GO",
            "qualifying_contracts": 0,
            "external_action_allowed": False,
        }

    monkeypatch.setattr(saas, "assess_owned_run_qualification", fake_qualification)
    path = f"/api/saas/runs/{run_id}/qualification"
    no_auth = client.get(path)
    assert no_auth.status_code == 401
    other_tenant = client.get(path, headers=_auth(token_b))
    assert other_tenant.status_code in (403, 404)
    assert not observed
    owned = client.get(path, headers=_auth(token_a))
    assert owned.status_code == 200, owned.text
    assert owned.json()["competitive_recommendation"] == "NO_GO"
    assert observed == [(run_id, tenant_a["customer_id"])]

    monkeypatch.setattr(
        saas, "get_uploaded_demo_report",
        lambda _: SimpleNamespace(
            run_id=run_id, report_title="Тендер", recommendation="NEEDS_REVIEW",
            manual_checks=["Проверить ТЗ"], executive_summary="Обзор",
            sections=[],
        ),
    )
    report = client.get(f"/api/saas/runs/{run_id}/report", headers=_auth(token_a))
    assert report.status_code == 200, report.text
    assert report.json()["qualification"]["competitive_recommendation"] == "NO_GO"
    assert report.json()["recommendation"] == "NEEDS_REVIEW"
    assert report.json()["external_action_allowed"] is False
    foreign = client.get(f"/api/saas/runs/{run_id}/report", headers=_auth(token_b))
    assert foreign.status_code in (403, 404)
    assert len(observed) == 2


def test_saas_viewer_report_does_not_expose_private_reference_list(client, monkeypatch):
    from types import SimpleNamespace

    from src.modules.saas_foundation import router as saas

    _tenant, owner = _seed(client, "ООО Приватность референсов")
    _legal(client, owner)
    upload = client.post(
        "/api/saas/runs",
        headers=_auth(owner),
        data={"tender_title": "Аудит", "procurement_customer_name": "Заказчик"},
        files=[("files", ("contract.txt", b"test contract", "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    run_id = upload.json()["run_id"]
    invitation = client.post(
        "/api/saas/invitations", headers=_auth(owner),
        json={"role": "viewer", "acquisition_channel": "referral"},
    )
    assert invitation.status_code == 200, invitation.text
    viewer_token = client.post(
        "/api/saas/invitations/redeem",
        json={
            "invitation_code": invitation.json()["invitation_code"],
            "display_name": "Viewer",
        },
    ).json()["access_token"]
    _legal(client, viewer_token)
    monkeypatch.setattr(
        saas, "assess_owned_run_qualification",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("private reference list must not be loaded for viewer")
        ),
    )
    monkeypatch.setattr(
        saas, "get_uploaded_demo_report",
        lambda _: SimpleNamespace(
            run_id=run_id, report_title="Тендер", recommendation="NEEDS_REVIEW",
            manual_checks=[], executive_summary="Описание", sections=[],
        ),
    )
    assert client.get(
        f"/api/saas/runs/{run_id}/qualification",
        headers=_auth(viewer_token),
    ).status_code == 403
    report = client.get(f"/api/saas/runs/{run_id}/report", headers=_auth(viewer_token))
    assert report.status_code == 200, report.text
    assert report.json()["qualification"]["source_status"] == "REFERENCE_ACCESS_RESTRICTED"
    assert "qualifying_contracts" not in report.json()["qualification"]


def test_owner_reference_list_optimistic_version_and_explicit_zero(client):
    """Missing != complete zero, stale edit is 409; previous version remains immutable."""
    _tenant, owner = _seed(client, "ООО Версионированные референсы")
    _legal(client, owner)
    endpoint = "/api/saas/qualification/references"
    unseen = client.get(endpoint, headers=_auth(owner))
    assert unseen.status_code == 200
    assert unseen.json()["state"] == "UNKNOWN"
    assert unseen.json()["fact_version"] is None

    snapshot = {
        "schema_version": "completed-contract-references-v1",
        "as_of_date": "2026-10-13",
        "completeness": "PARTIAL",
        "owner_confirmed": False,
        "contracts": [],
    }
    payload = {
        "source_ref": "OWNER_DRAFT_ZERO_NOT_CONFIRMED",
        "snapshot": snapshot,
        "expected_version": 0,
    }
    incomplete = client.post(endpoint, headers=_auth(owner), json=payload)
    assert incomplete.status_code == 201, incomplete.text
    assert incomplete.json()["fact_version"] == 1

    payload["snapshot"] = {
        **snapshot, "completeness": "COMPLETE", "owner_confirmed": True,
    }
    payload["source_ref"] = "OWNER_CONFIRMED_ZERO_2026-10-13"
    stale = client.post(endpoint, headers=_auth(owner), json=payload)
    assert stale.status_code == 409, stale.text
    assert client.get(endpoint, headers=_auth(owner)).json()["snapshot"]["completeness"] == "PARTIAL"

    payload["expected_version"] = 1
    second = client.post(endpoint, headers=_auth(owner), json=payload)
    assert second.status_code == 201, second.text
    assert second.json()["fact_version"] == 2
    current = client.get(endpoint, headers=_auth(owner))
    assert current.json()["fact_version"] == 2
    assert current.json()["snapshot"]["completeness"] == "COMPLETE"
    assert current.json()["snapshot"]["contracts"] == []

    # An out-of-date browser cannot change an owner-confirmed current list.
    again = client.post(endpoint, headers=_auth(owner), json=payload)
    assert again.status_code == 409
    invalid = client.post(endpoint, headers=_auth(owner), json={
        "source_ref": "IMPROPER_UNCONFIRMED_ZERO",
        "expected_version": 2,
        "snapshot": {**snapshot, "completeness": "COMPLETE", "owner_confirmed": False},
    })
    assert invalid.status_code == 422
    assert client.get(endpoint, headers=_auth(owner)).json()["fact_version"] == 2


def test_completed_contract_entry_requires_signed_act_and_document_refs(client):
    _tenant, owner = _seed(client, "ООО Верификация актов")
    _legal(client, owner)
    ep = "/api/saas/qualification/references"
    base = {
        "source_ref": "OWNER_COMPLETED_CONTRACTS",
        "expected_version": 0,
        "snapshot": {
            "schema_version": "completed-contract-references-v1",
            "as_of_date": "2026-10-13",
            "completeness": "COMPLETE",
            "owner_confirmed": True,
            "contracts": [{
                "law": "44fz", "contract_number": "КТ-001", "subject": "website",
                "chatbot_in_scope": True, "completed": True,
                "acceptance_signed_at": "2026-08-01",
                "contract_document_ref": "COMPANY_DOC_CONTRACT_KT001",
                "signed_final_act_ref": "COMPANY_DOC_FINAL_ACT_KT001",
            }],
        },
    }
    good = client.post(ep, headers=_auth(owner), json=base)
    assert good.status_code == 201, good.text
    assert client.get(ep, headers=_auth(owner)).json()["snapshot"]["contracts"][0]["completed"]
    # A contract marked complete cannot be saved without the signed final act.
    base["expected_version"] = 1
    base["snapshot"]["contracts"][0]["signed_final_act_ref"] = None
    bad = client.post(ep, headers=_auth(owner), json=base)
    assert bad.status_code == 422
    assert client.get(ep, headers=_auth(owner)).json()["fact_version"] == 1
