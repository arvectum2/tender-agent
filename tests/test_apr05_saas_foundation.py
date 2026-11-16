"""APR-05 tenant isolation, invitation lifecycle, legal and monthly entitlement checks."""
from __future__ import annotations

import base64
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_apr03b_archived_eis_full_source_integrity import case as archived_case  # noqa: F401

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


@pytest.mark.parametrize("real_private_original", [False, True])
def test_http_source_bound_1c_qualification_through_tenant_roles(
    client, monkeypatch, tmp_path, real_private_original,
):
    """Real HTTP auth/owned_run with original 44-FZ sources; never production DB."""
    import hashlib
    import io
    import json
    import os
    import shutil
    import types
    import zipfile
    from pathlib import Path

    from src.modules.company_profile_store import (
        qualification_run_composite_pdf as pdf_observer,
    )
    from src.modules.company_profile_store import (
        qualification_run_service as qualification,
    )
    from src.modules.saas_foundation import router as saas

    private_root = os.environ.get("TA_TEST_ORIGINAL_EIS_44_CASE_DIR", "")
    if real_private_original and not private_root:
        pytest.skip("Private original EIS source not present in CI; Mac mini only")
    receipt_path = (
        Path(__file__).resolve().parents[1]
        / "docs/acceptance/alternate_44_1c_scoring_original_receipt_2026-10-13.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    number = receipt["procurement_number"]
    uid = receipt["scoring_document_uid"]
    url = (
        "https://zakupki.gov.ru/44fz/filestore/public/1.0/"
        f"download/priz/file.html?uid={uid}"
    )
    filename = receipt["scoring_document_name"]
    run_folder = tmp_path / "source-pinned-run"
    run_folder.mkdir()
    if real_private_original:
        source = Path(private_root)
        soap_source = source / "documentation-archive.zip"
        pdf_source = next((source / "evaluation").glob("*.pdf"))
        assert hashlib.sha256(soap_source.read_bytes()).hexdigest() == (
            receipt["original_soap_archive_sha256"]
        )
        assert hashlib.sha256(pdf_source.read_bytes()).hexdigest() == (
            receipt["scoring_document_sha256"]
        )
        shutil.copyfile(soap_source, run_folder / "original-soap.zip")
        shutil.copyfile(pdf_source, run_folder / "evaluation.pdf")
    else:
        pdf_bytes = b"%PDF-1.7\nsynthetic-bound-test-source\n"
        xml = (
            "<root><epNotificationEOK2020>"
            f"<purchaseNumber>{number}</purchaseNumber>"
            "<versionNumber>2</versionNumber>"
            "<endDT>2026-10-22T08:00:00+03:00</endDT>"
            "<attachmentInfo>"
            f"<publishedContentId>{uid}</publishedContentId>"
            f"<fileName>{filename}</fileName>"
            f"<fileSize>{len(pdf_bytes)}</fileSize>"
            f"<url>{url}</url>"
            "</attachmentInfo></epNotificationEOK2020></root>"
        ).encode()
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as z:
            z.writestr(f"epNotificationEOK2020_{number}_2.xml", xml)
        (run_folder / "original-soap.zip").write_bytes(archive_bytes.getvalue())
        (run_folder / "evaluation.pdf").write_bytes(pdf_bytes)
    soap_bytes = (run_folder / "original-soap.zip").read_bytes()
    pdf_bytes = (run_folder / "evaluation.pdf").read_bytes()
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": number,
        "archive_downloaded": True,
        "getdocs_status": "completed",
        "subsystem_type": "PRIZ",
        "token_owner": "individual",
        "archive_source_host": "int.zakupki.gov.ru",
        "archive_stored_name": "original-soap.zip",
        "original_getdocs_archive_sha256": hashlib.sha256(soap_bytes).hexdigest(),
        "files": [{
            "source_type": "notice_xml_attachments",
            "original_name": filename,
            "stored_name": "evaluation.pdf",
            "source_download_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "source_url": url,
        }],
    }
    tenant, owner = _seed(client, "ООО Изолированная экспертиза 1С")
    _, outsider = _seed(client, "ООО Чужой клиент 1С")
    _legal(client, owner)
    _legal(client, outsider)
    upload = client.post(
        "/api/saas/runs", headers=_auth(owner),
        data={"tender_title": "Исходная закупка 1С", "procurement_customer_name": "Заказчик"},
        files=[("files", ("initial.txt", b"test-only synthetic placeholder", "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    run_id = upload.json()["run_id"]
    invitation = client.post("/api/saas/invitations", headers=_auth(owner), json={
        "role": "viewer", "acquisition_channel": "referral",
    })
    assert invitation.status_code == 200, invitation.text
    viewer = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": invitation.json()["invitation_code"],
        "display_name": "Read-only viewer",
    })
    assert viewer.status_code == 201, viewer.text
    viewer_token = viewer.json()["access_token"]
    _legal(client, viewer_token)

    monkeypatch.setattr(qualification, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(qualification, "get_demo_run_input_dir", lambda _: run_folder)
    if not real_private_original:
        fake_text = """ПОРЯДОК
Рассмотрения и оценки заявок на участие в конкурсе
1. Цена контракта, 60 100
4. Квалификация 40 100
    контракта 5 характеристика
    наличие у 95 характеристика
количество исполненных Контрактов (договоров)
перечень специалистов и иных работников
"""
        monkeypatch.setattr(
            pdf_observer.subprocess, "run",
            lambda *_args, **_kwargs: types.SimpleNamespace(
                stdout=fake_text.encode("utf-8"),
            ),
        )
    monkeypatch.setattr(
        saas, "get_uploaded_demo_report",
        lambda _: types.SimpleNamespace(
            run_id=run_id,
            report_title="Подтверждённый оригинал 1С",
            recommendation="NEEDS_REVIEW",
            manual_checks=["Проверить сведения о специалистах"],
            executive_summary="Составные критерии оценки", sections=[],
        ),
    )
    ep = f"/api/saas/runs/{run_id}/qualification"
    report_ep = f"/api/saas/runs/{run_id}/report"
    assert client.get(ep).status_code == 401
    assert client.get(ep, headers=_auth(outsider)).status_code == 404
    assert client.get(report_ep, headers=_auth(outsider)).status_code == 404
    assert client.get(ep, headers=_auth(viewer_token)).status_code == 403

    owner_result = client.get(ep, headers=_auth(owner))
    assert owner_result.status_code == 200, owner_result.text
    q = owner_result.json()
    assert q["competitive_recommendation"] == "NOT_ASSESSED"
    assert q["qualifying_contracts"] is None
    assert q["criterion_source"]["price_weight_percent"] == 60
    assert q["criterion_source"]["qualification_weight_percent"] == 40
    assert q["criterion_source"]["qualification_subweights_percent"] == {
        "completed_contract_count": 5, "specialists": 95,
    }
    assert q["external_action_allowed"] is False
    report = client.get(report_ep, headers=_auth(owner))
    assert report.status_code == 200, report.text
    assert report.json()["qualification"]["competitive_recommendation"] == "NOT_ASSESSED"
    assert report.json()["human_control_required"] is True
    assert report.json()["external_action_allowed"] is False
    viewer_report = client.get(report_ep, headers=_auth(viewer_token))
    assert viewer_report.status_code == 200, viewer_report.text
    assert viewer_report.json()["qualification"]["source_status"] == (
        "REFERENCE_ACCESS_RESTRICTED"
    )
    assert "criterion_source" not in viewer_report.json()["qualification"]
    assert "qualifying_contracts" not in viewer_report.json()["qualification"]

    # Only the temporary copy is damaged, after the successful owner report.
    pdf_copy = run_folder / "evaluation.pdf"
    content = pdf_copy.read_bytes()
    pdf_copy.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
    changed = client.get(ep, headers=_auth(owner))
    assert changed.status_code == 200
    assert changed.json()["competitive_recommendation"] == "NOT_ASSESSED"
    assert changed.json()["source_status"] == "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
    assert "criterion_source" not in changed.json()
    assert tenant["customer_id"] != client.get(
        "/api/saas/profile", headers=_auth(outsider)
    ).json()["customer_id"]
    if real_private_original:
        assert hashlib.sha256(pdf_source.read_bytes()).hexdigest() == (
            receipt["scoring_document_sha256"]
        )


def test_company_portfolio_same_public_reference_distinct_cases_and_decisions(client, session):
    from src.modules.customer_pilot.models import ProcurementCase
    from src.modules.deal_registry.models import Deal
    from src.modules.saas_foundation.models import CompanyPortfolioDecision

    a, owner_a = _seed(client, "Изолированный тест A")
    b, owner_b = _seed(client, "Изолированный тест B")
    _legal(client, owner_a)
    _legal(client, owner_b)
    base = "/api/saas/company-portfolio/cases"
    body = {"registry_number": "0123456789012345678"}
    assert client.get(base).status_code == 401
    assert client.post(base, headers=_auth(owner_a), json={**body, "customer_id": b["customer_id"]}).status_code == 422
    ca = client.post(base, headers=_auth(owner_a), json=body)
    cb = client.post(base, headers=_auth(owner_b), json=body)
    assert ca.status_code == cb.status_code == 201, (ca.text, cb.text)
    ca, cb = ca.json(), cb.json()
    assert ca["case_id"] != cb["case_id"]
    assert ca["registry_number"] == cb["registry_number"]
    assert ca["source_verified"] is False and ca["decision"] is None
    assert client.post(base, headers=_auth(owner_a), json=body).json()["case_id"] == ca["case_id"]
    aa, bb = f"{base}/{ca['case_id']}", f"{base}/{cb['case_id']}"
    go = {"action": "GO", "rationale": "Только A", "expected_revision": 0, "idempotency_key": "case-key-001"}
    no = {**go, "action": "NO_GO", "rationale": "Только B"}
    first = client.post(aa + "/decisions", headers=_auth(owner_a), json=go)
    second = client.post(bb + "/decisions", headers=_auth(owner_b), json=no)
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert client.post(aa + "/decisions", headers=_auth(owner_a), json=go).json() == first.json()
    assert client.post(aa + "/decisions", headers=_auth(owner_a), json=no).status_code == 409
    assert client.post(aa + "/decisions", headers=_auth(owner_a), json={**go, "idempotency_key": "other-key-001"}).status_code == 409
    assert client.get(aa, headers=_auth(owner_b)).status_code == 404
    assert client.get(aa + "/decisions", headers=_auth(owner_b)).status_code == 404
    assert client.post(aa + "/decisions", headers=_auth(owner_b), json=no).status_code == 404
    assert client.get(bb, headers=_auth(owner_a)).status_code == 404
    list_a = client.get(base, headers=_auth(owner_a)).json()
    list_b = client.get(base, headers=_auth(owner_b)).json()
    assert list_a["customer_id"] == a["customer_id"]
    assert [x["decision"]["action"] for x in list_a["items"]] == ["GO"]
    assert [x["decision"]["action"] for x in list_b["items"]] == ["NO_GO"]
    assert "Только B" not in str(list_a)
    assert all(not x["external_submission_allowed"] for x in list_a["items"] + list_b["items"])
    assert session.query(ProcurementCase).count() == 2
    assert session.query(CompanyPortfolioDecision).count() == 2
    assert session.query(Deal).count() == 0


def test_company_portfolio_role_legal_history_and_defer(client, session):
    _, owner = _seed(client, "Тест ролей портфеля")
    base = "/api/saas/company-portfolio/cases"
    body = {"registry_number": "0123456789012345678"}
    assert client.post(base, headers=_auth(owner), json=body).status_code == 428
    _legal(client, owner)
    case = client.post(base, headers=_auth(owner), json=body).json()
    path = f"{base}/{case['case_id']}/decisions"
    invite = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": "viewer", "acquisition_channel": "referral"}).json()
    viewer = client.post("/api/saas/invitations/redeem", json={"invitation_code": invite["invitation_code"], "display_name": "Viewer"}).json()["access_token"]
    _legal(client, viewer)
    go = {"action": "GO", "rationale": "Подготовить проверку", "expected_revision": 0, "idempotency_key": "event-key-001"}
    assert client.post(base, headers=_auth(viewer), json=body).status_code == 403
    assert client.post(path, headers=_auth(viewer), json=go).status_code == 403
    assert client.get(base, headers=_auth(viewer)).status_code == 200
    assert client.post(path, headers=_auth(owner), json=go).status_code == 200
    defer = {**go, "action": "DEFER", "expected_revision": 1, "idempotency_key": "event-key-002"}
    assert client.post(path, headers=_auth(owner), json=defer).status_code == 422
    assert client.post(path, headers=_auth(owner), json={**defer, "deferred_until": "2000-01-01T00:00:00Z"}).status_code == 422
    future = (service.now_utc() + timedelta(days=1)).isoformat()
    assert client.post(path, headers=_auth(owner), json={**defer, "deferred_until": future}).status_code == 200
    history = client.get(path, headers=_auth(viewer)).json()["items"]
    assert [x["action"] for x in history] == ["DEFER", "GO"]
    assert [x["revision"] for x in history] == [2, 1]
    assert client.get(path + "?limit=1", headers=_auth(owner)).json()["has_more"] is True


def test_company_search_context_reads_only_own_versioned_criteria(client):
    _, a = _seed(client, "Тест поиска A")
    _, b = _seed(client, "Тест поиска B")
    path = "/api/saas/company-portfolio/search-context"
    assert client.get(path, headers=_auth(a)).status_code == 428
    _legal(client, a)
    _legal(client, b)
    assert client.get(path, headers=_auth(a)).json()["profile_state"] == "MISSING"
    assert client.put("/api/saas/profile", json=_profile(), headers=_auth(a)).status_code == 200
    own = client.get(path, headers=_auth(a)).json()
    assert own["profile_version"] == 1 and own["criteria"]["keywords"] == ["разработка"]
    assert own["automatic_search_enabled"] is False
    other = client.get(path, headers=_auth(b)).json()
    assert other["criteria"] is None and other["profile_state"] == "MISSING"
    assert "qualification" not in own and "commercial" not in own


def test_company_evidence_owned_archive_binding_profile_staleness_and_tamper(client, session, monkeypatch, archived_case):  # noqa: F811
    from fastapi import HTTPException
    from test_apr03b_archived_eis_full_source_integrity import NUMBER, RUN

    from src.modules.saas_foundation import company_case_evidence as evidence
    from src.modules.saas_foundation.models import (
        CompanyPortfolioEvidence,
        SaasMember,
        SaasRun,
    )

    tenant_a, a = _seed(client, "Тест доказательств A")
    _, b = _seed(client, "Тест доказательств B")
    _legal(client, a)
    _legal(client, b)
    for token in (a, b):
        assert client.put("/api/saas/profile", headers=_auth(token), json=_profile()).status_code == 200
    owner = session.scalar(select(SaasMember).where(SaasMember.tenant_id == tenant_a["tenant_id"]))
    session.add(SaasRun(tenant_id=tenant_a["tenant_id"], run_id=RUN, created_by_member_id=owner.id))
    session.commit()
    base = "/api/saas/company-portfolio/cases"
    def make(token, number):
        res = client.post(base, headers=_auth(token), json={"registry_number": number})
        assert res.status_code == 201, res.text
        return f"{base}/{res.json()['case_id']}/evidence"
    own, foreign, mismatch = make(a, NUMBER), make(b, NUMBER), make(a, "0123456789012345678")
    payload = {"run_id": RUN, "expected_profile_version": 1}
    assert client.post(own, headers=_auth(b), json=payload).status_code == 404
    assert client.post(foreign, headers=_auth(b), json=payload).status_code == 404
    assert client.post(mismatch, headers=_auth(a), json=payload).status_code == 409
    assert client.post(own, headers=_auth(a), json={**payload, "expected_profile_version": 2}).status_code == 409
    assert client.post(own, headers=_auth(a), json={**payload, "source_snapshot_sha256": "fake"}).status_code == 422
    bound = client.post(own, headers=_auth(a), json=payload)
    assert bound.status_code == 201, bound.text
    binding = bound.json()
    assert binding["profile_version"] == 1 and binding["current_live_notice_status_verified"] is False
    replay = client.post(own, headers=_auth(a), json=payload)
    assert replay.json()["binding_id"] == binding["binding_id"]
    path = f"{own}/{binding['binding_id']}"
    assert client.get(path, headers=_auth(b)).status_code == 404
    assert client.get(f"{foreign}/{binding['binding_id']}", headers=_auth(b)).status_code == 404
    assert client.get(foreign, headers=_auth(b)).json()["items"] == []
    def missing_report(run_id):
        raise HTTPException(404, "Report not available")
    monkeypatch.setattr(evidence, "get_uploaded_demo_report", missing_report)
    absent = client.get(path, headers=_auth(a)).json()
    assert absent["report_status"] == "REPORT_UNAVAILABLE" and absent["qualification"] is None
    observed = []
    monkeypatch.setattr(evidence, "get_uploaded_demo_report", lambda _: SimpleNamespace(run_id=RUN, decision_core={"procurement_regime": "44fz"}))
    def qualify(session, *, run_id, customer_id, as_of):
        observed.append((run_id, customer_id))
        return {"competitive_recommendation": "NOT_ASSESSED", "external_action_allowed": False}
    monkeypatch.setattr(evidence, "assess_owned_run_qualification", qualify)
    read = client.get(path, headers=_auth(a))
    assert read.status_code == 200, read.text
    assert read.json()["archived_source_snapshot_verified"] is True
    assert read.json()["screening"]["customer_id"] == tenant_a["customer_id"]
    assert read.json()["screening"]["decision"] == "HUMAN_REVIEW_REQUIRED"
    assert observed == [(RUN, tenant_a["customer_id"])]
    assert client.put("/api/saas/profile", headers=_auth(a), json=_profile()).status_code == 200
    stale = client.get(path, headers=_auth(a)).json()
    assert stale["profile_state"] == "SUPERSEDED" and stale["current_profile_version"] == 2
    assert stale["report_status"] == "PROFILE_REVIEW_REQUIRED" and stale["screening"] is None
    assert len(observed) == 1
    assert client.post(own, headers=_auth(a), json=payload).status_code == 409
    fresh = client.post(own, headers=_auth(a), json={**payload, "expected_profile_version": 2})
    assert fresh.status_code == 201 and fresh.json()["binding_id"] != binding["binding_id"]
    assert session.query(CompanyPortfolioEvidence).count() == 2
    root, _ = archived_case
    attachment = root / "input/original-2.bin"
    attachment.write_bytes(b"x" * attachment.stat().st_size)
    assert client.get(path, headers=_auth(a)).status_code == 409
    assert client.get(f"{own}/{fresh.json()['binding_id']}", headers=_auth(a)).status_code == 409
    assert len(observed) == 1


def test_mobile_company_identity_comes_from_authenticated_principal(client):
    a, token_a = _seed(client, "Тестовая компания Alpha")
    b, token_b = _seed(client, "Тестовая компания Beta")
    for tenant, token, expected in ((a, token_a, "Тестовая компания Alpha"), (b, token_b, "Тестовая компания Beta")):
        result = client.get("/api/saas/me", headers=_auth(token), params={"customer_id": "foreign"})
        assert result.status_code == 200
        assert result.json()["customer_id"] == tenant["customer_id"]
        assert result.json()["company_name"] == expected
        assert result.json()["legal_accepted"] is False
    assert client.get("/api/saas/me", headers=_auth("mobile_fake_token")).status_code == 401


def test_company_portfolio_distinct_members_share_revisioned_decision_history(client):
    _, owner = _seed(client, "Тест общего журнала веб и iOS")
    _legal(client, owner)
    invite = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": "admin", "acquisition_channel": "referral"}).json()
    member = client.post("/api/saas/invitations/redeem", json={"invitation_code": invite["invitation_code"], "display_name": "Тестовый администратор"}).json()
    admin = member["access_token"]
    _legal(client, admin)
    base = "/api/saas/company-portfolio/cases"
    case = client.post(base, headers=_auth(owner), json={"registry_number": "0123456789012345678"}).json()
    detail = f"{base}/{case['case_id']}"
    owner_draft = {"action": "GO", "rationale": "Интерфейс A", "expected_revision": 0, "idempotency_key": "shared-fixture-001"}
    before = client.get(detail, headers=_auth(admin)).json()
    assert before["revision"] == 0
    first = client.post(detail + "/decisions", headers=_auth(owner), json=owner_draft)
    assert first.status_code == 200
    assert client.get(detail, headers=_auth(admin)).json()["decision"] == first.json()
    assert client.post(detail + "/decisions", headers=_auth(admin), json=owner_draft).status_code == 409
    stale = {**owner_draft, "idempotency_key": "shared-fixture-002", "action": "NO_GO"}
    assert client.post(detail + "/decisions", headers=_auth(admin), json=stale).status_code == 409
    updated = {**stale, "rationale": "Интерфейс B", "expected_revision": 1}
    second = client.post(detail + "/decisions", headers=_auth(admin), json=updated)
    assert second.status_code == 200
    assert second.json()["decided_by_member_id"] == member["member_id"]
    assert client.get(detail, headers=_auth(owner)).json()["decision"] == second.json()
    assert client.post(detail + "/decisions", headers=_auth(admin), json=updated).json() == second.json()
    history = client.get(detail + "/decisions", headers=_auth(owner)).json()["items"]
    assert [d["revision"] for d in history] == [2, 1]
    assert len({d["decided_by_member_id"] for d in history}) == 2
    assert client.get(base, headers=_auth(owner)).json()["items"][0]["external_submission_allowed"] is False


def _enable_company_discovery(monkeypatch):
    settings = saas.get_settings().model_copy(update={"saas_company_discovery_enabled": True})
    monkeypatch.setattr(saas, "get_settings", lambda: settings)


def test_company_discovery_frozen_plan_scope_and_step_receipts(client, session, monkeypatch):
    from src.modules.customer_pilot.models import ProcurementCase
    from src.modules.deal_registry.models import Deal
    from src.modules.saas_foundation import company_discovery as discovery
    from src.modules.saas_foundation.models import CompanyDiscoveryRun

    _, a = _seed(client, "Тест поиска A")
    _, b = _seed(client, "Тест поиска B")
    _legal(client, a)
    _legal(client, b)
    root = "/api/saas/company-portfolio/discovery"
    payload = {"expected_profile_version": 1}
    calls = []

    def search(**kwargs):
        calls.append(kwargs)
        if kwargs["query"] == "сбой":
            return {"outcome": "source_unavailable"}
        cards = [{"reestr_number": "0123456789012345678", "title": "Разработка системы", "initial_price": 500000,
                  "source": "public_eis_html_44fz", "law": "44fz", "relevance": {"global_private_score": 100}},
                 {"reestr_number": "0123456789012345679", "title": "Разработка лицензия", "initial_price": 500000,
                  "source": "public_eis_html_44fz", "law": "44fz"}]
        return {"outcome": "success_with_results", "source": "public_eis_html_44fz", "cards": cards,
                "has_more": True, "source_coverage_complete": False}

    monkeypatch.setattr(discovery, "search_public_44fz", search)
    assert client.post(root + "/runs", headers=_auth(a), json=payload).status_code == 404
    assert not calls
    _enable_company_discovery(monkeypatch)
    assert client.post(root + "/runs", headers=_auth(a), json=payload).status_code == 409
    profile = _profile()
    profile["criteria"].update(keywords=["разработка", "доработка", "сбой"], stop_words=["лицензия"])
    assert client.put("/api/saas/profile", headers=_auth(a), json=profile).status_code == 200
    assert client.post(root + "/runs", headers=_auth(a), json={**payload, "query": "injected"}).status_code == 422
    res = client.post(root + "/runs", headers=_auth(a), json=payload)
    assert res.status_code == 201, res.text
    run = res.json()
    assert not calls and run["status"] == "PENDING"
    assert client.post(root + "/runs", headers=_auth(a), json=payload).json()["run_id"] == run["run_id"]
    path = root + "/runs/" + run["run_id"]
    assert client.get(path, headers=_auth(b)).status_code == 404
    assert client.post(path + "/step", headers=_auth(b), json={"expected_step": 0}).status_code == 404
    assert client.get(root + "/latest", headers=_auth(b)).json()["run"] is None
    assert client.post(path + "/step", headers=_auth(a), json={"expected_step": 2}).status_code == 409
    initial = client.post(path + "/step", headers=_auth(a), json={"expected_step": 0})
    assert initial.status_code == 200, initial.text
    first = initial.json()
    assert first["status"] == "IN_PROGRESS" and first["completed_steps"] == 1
    assert first["discovery_incomplete"] is True
    assert len(first["candidates"]) == 1 and first["step_receipts"][0]["excluded_cards"] == 1
    assert "global_private_score" not in str(first)
    assert calls[0]["query"] == "разработка" and calls[0]["region"] == "Москва"
    assert calls[0]["apply_supplier_relevance"] is False and calls[0]["backfill_page_limit"] == 2
    assert calls[0]["price_from"] == 100000 and calls[0]["price_to"] == 900000
    assert client.post(path + "/step", headers=_auth(a), json={"expected_step": 0}).json() == first
    assert len(calls) == 1
    for index in (1, 2):
        finished = client.post(path + "/step", headers=_auth(a), json={"expected_step": index}).json()
    assert finished["status"] == "PARTIAL" and finished["completed_steps"] == 3
    assert len(finished["candidates"]) == 1 and finished["candidates"][0]["matched_steps"] == [0, 1]
    assert finished["step_receipts"][2]["outcome"] == "source_unavailable"
    assert all(call["date_from"] == run["plan"]["date_from"] for call in calls)
    assert len(calls) == 3
    assert session.query(CompanyDiscoveryRun).count() == 1
    assert session.query(ProcurementCase).count() == 0 and session.query(Deal).count() == 0
    assert client.get(path, headers=_auth(a)).json() == finished
    assert client.post("/api/saas/company-portfolio/cases", headers=_auth(a), json={"registry_number": finished["candidates"][0]["registry_number"]}).status_code == 201
    assert session.query(ProcurementCase).count() == 1


def test_company_discovery_stale_profile_and_explicit_empty(client, monkeypatch):
    from src.modules.saas_foundation import company_discovery as discovery

    _enable_company_discovery(monkeypatch)
    _, a = _seed(client, "Тест устаревшего профиля")
    _, b = _seed(client, "Тест пустого поиска")
    _legal(client, a)
    _legal(client, b)
    profile = _profile()
    profile["criteria"]["regions"] = []
    for token in (a, b):
        assert client.put("/api/saas/profile", headers=_auth(token), json=profile).status_code == 200
    calls = []
    def empty(**kwargs):
        calls.append(kwargs)
        return {"outcome": "success_empty", "source": "public_eis_html_44fz", "cards": [], "has_more": False, "source_coverage_complete": True}
    monkeypatch.setattr(discovery, "search_public_44fz", empty)
    root = "/api/saas/company-portfolio/discovery/runs"
    payload = {"expected_profile_version": 1}
    run_a = client.post(root, headers=_auth(a), json=payload).json()["run_id"]
    run_b = client.post(root, headers=_auth(b), json=payload).json()["run_id"]
    assert client.put("/api/saas/profile", headers=_auth(a), json=profile).status_code == 200
    stale = client.post(f"{root}/{run_a}/step", headers=_auth(a), json={"expected_step": 0}).json()
    assert stale["status"] == "STALE_PROFILE" and stale["completed_steps"] == 0
    assert not calls
    assert client.post(root, headers=_auth(a), json={"expected_profile_version": 2}).status_code == 409
    completed = client.post(f"{root}/{run_b}/step", headers=_auth(b), json={"expected_step": 0}).json()
    assert completed["status"] == "COMPLETED" and completed["discovery_incomplete"] is False
    assert completed["candidates"] == [] and len(calls) == 1


def test_company_commercial_identity_and_shared_portfolio(client, session):
    from src.modules.customer_pilot.models import ProcurementCase
    from src.modules.deal_registry.models import Deal

    _, a = _seed(client, "Коммерция A")
    _, b = _seed(client, "Коммерция B")
    _legal(client, a)
    _legal(client, b)
    endpoint = "/api/saas/company-portfolio/commercial-cases"
    b2b = "https://www.b2b-center.ru/app/market-next/fixture/tender-1234567/"
    workspace = "https://workspace.ru/tenders/fixture-1234567/"
    for bad in (b2b + "?token=fixture", "https://evil.invalid/tenders/fixture-1234567/", workspace + "#x", b2b.replace("www.b2b-center.ru", "www.b2b-center.ru.evil.invalid")):
        assert client.post(endpoint, headers=_auth(a), json={"source_url": bad}).status_code == 422
    def save(token, url):
        r = client.post(endpoint, headers=_auth(token), json={"source_url": url})
        assert r.status_code == 201, r.text
        return r.json()
    one, two, other = save(a, b2b), save(a, workspace), save(b, b2b)
    assert len({one["case_id"], two["case_id"], other["case_id"]}) == 3
    assert one["external_id"] == two["external_id"] == "1234567"
    assert one["source_platform"] == "b2bcenter" and two["source_platform"] == "workspace"
    assert one["registry_number"] is None and one["source_verified"] is False and one["source_url"] == b2b
    assert save(a, b2b.replace("/app/market-next/fixture/", "/market/changed/"))["case_id"] == one["case_id"]
    assert save(a, b2b)["source_url"] == b2b
    base = "/api/saas/company-portfolio/cases"
    eis = client.post(base, headers=_auth(a), json={"registry_number": "0123456789012345678"}).json()
    assert eis["source_platform"] == "eis" and eis["external_id"] == eis["registry_number"]
    assert {c["case_id"] for c in client.get(base, headers=_auth(a)).json()["items"]} == {one["case_id"], two["case_id"], eis["case_id"]}
    path = f"{base}/{one['case_id']}"
    assert client.get(path, headers=_auth(b)).status_code == 404
    assert client.post(path + "/evidence", headers=_auth(a), json={"run_id": "toa-run-20261116000000-abcdef", "expected_profile_version": 1}).status_code == 409
    decision = client.post(path + "/decisions", headers=_auth(a), json={"action": "GO", "rationale": "Внутренняя проверка", "expected_revision": 0, "idempotency_key": "commercial-fixture-1"})
    assert decision.status_code == 200
    assert client.get(f"{base}/{two['case_id']}", headers=_auth(a)).json()["decision"] is None
    assert session.query(ProcurementCase).count() == 4 and session.query(Deal).count() == 0


def test_company_mixed_commercial_discovery_uses_own_keywords_and_namespaces(client, session, monkeypatch):
    from src.modules.saas_foundation import company_discovery as discovery
    from src.modules.saas_foundation.commercial_sources import parse_index

    _enable_company_discovery(monkeypatch)
    _, a = _seed(client, "Поиск по индексу")
    _legal(client, a)
    profile = _profile()
    profile["criteria"].update(keywords=["разработка"], stop_words=["лицензия"], regions=[])
    assert client.put("/api/saas/profile", headers=_auth(a), json=profile).status_code == 200
    b2b = "https://www.b2b-center.ru/market/fixture/tender-1234567/"
    workspace = "https://workspace.ru/tenders/fixture-1234567/"
    raw_rss = f'<rss><channel><item><title>разработка сайта</title><link>{workspace}</link></item><item><title>разработка лицензия</title><link>https://workspace.ru/tenders/other-1234568/</link></item></channel></rss>'.encode()
    raw_b2b = f'<html><body><div>Опубликовано: 16.11.2026 Подать заявку до: 20.11.2026 Закупка №1234567 разработка сайта <a href="{b2b}">разработка</a></div></body></html>'.encode()
    calls = []
    def search(index, keywords, exclusions):
        calls.append((index, keywords, exclusions))
        return parse_index(index, raw_rss if index == "workspace_rss" else raw_b2b, keywords, exclusions)
    monkeypatch.setattr(discovery, "search_index", search)
    monkeypatch.setattr(discovery, "search_public_44fz", lambda **_: {"source": "public_eis_html_44fz", "outcome": "success_empty", "cards": [], "has_more": False, "source_coverage_complete": True})
    endpoint = "/api/saas/company-portfolio/discovery/runs"
    assert client.post(endpoint, headers=_auth(a), json={"expected_profile_version": 1, "commercial_indexes": ["https://evil.invalid/"]}).status_code == 422
    res = client.post(endpoint, headers=_auth(a), json={"expected_profile_version": 1, "commercial_indexes": ["workspace_rss", "b2bcenter:crm-sistemy"]})
    assert res.status_code == 201, res.text
    run = res.json()
    assert len(run["plan"]["steps"]) == 3
    for i in range(3):
        result = client.post(f"{endpoint}/{run['run_id']}/step", headers=_auth(a), json={"expected_step": i})
        assert result.status_code == 200, result.text
    result = result.json()
    assert result["status"] == "PARTIAL" and result["discovery_incomplete"] is True
    assert {(c["source_platform"], c["external_id"]) for c in result["candidates"]} == {("workspace", "1234567"), ("b2bcenter", "1234567")}
    assert all(c["observed_price"] is None and c["source_verified"] is False for c in result["candidates"])
    assert all(kw == ["разработка"] and exc == ["лицензия"] for _, kw, exc in calls)
    assert len(result["step_receipts"][1]["index_sha256"]) == 64
    assert client.post(endpoint, headers=_auth(a), json={"expected_profile_version": 1}).status_code == 409


def test_commercial_index_rejects_ambiguous_card_and_unsafe_rss():
    import pytest

    from src.modules.saas_foundation.commercial_sources import parse_index

    one = "https://www.b2b-center.ru/market/fixture/tender-1234567/"
    two = "https://www.b2b-center.ru/market/fixture/tender-1234568/"
    raw = f'<html><body><div>Опубликовано: 16.11.2026 Подать заявку до: 20.11.2026 Закупка №1234567 разработка <a href="{one}">A</a><a href="{two}">B</a></div></body></html>'.encode()
    assert parse_index("b2bcenter:crm-sistemy", raw, ["разработка"], [])["cards"] == []
    raw = b'<!DOCTYPE rss [<!ENTITY fixture "test">]><rss><channel><title>&fixture;</title></channel></rss>' + b' ' * 100
    with pytest.raises(ValueError, match="XML declarations"):
        parse_index("workspace_rss", raw, ["test"], [])


def test_company_schedule_opt_in_scoped_retry_and_resume(client, session, monkeypatch):
    from src.modules.saas_foundation import company_discovery as discovery
    from src.modules.saas_foundation import company_schedule as schedule
    from src.modules.saas_foundation.models import CompanyDiscoverySchedule

    tenant, a = _seed(client, "Расписание A")
    _, b = _seed(client, "Расписание B")
    _legal(client, a)
    _legal(client, b)
    profile = _profile()
    profile["criteria"]["regions"] = []
    assert client.put("/api/saas/profile", headers=_auth(a), json=profile).status_code == 200
    root = "/api/saas/company-portfolio/discovery/schedule"
    payload = {"enabled": True, "expected_revision": 0, "expected_profile_version": 1, "hour_moscow": 0, "confirm_unattended_public_search": True}
    assert client.put(root, headers=_auth(a), json=payload).status_code == 409
    assert session.query(CompanyDiscoverySchedule).count() == 0
    settings = saas.get_settings().model_copy(update={"saas_company_discovery_enabled": True, "saas_company_schedule_enabled": True})
    monkeypatch.setattr(saas, "get_settings", lambda: settings)
    assert client.put(root, headers=_auth(a), json={**payload, "confirm_unattended_public_search": False}).status_code == 409
    assert client.put(root, headers=_auth(a), json={**payload, "expected_profile_version": 2}).status_code == 409
    saved = client.put(root, headers=_auth(a), json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["enabled"] and saved.json()["revision"] == 1
    assert client.put(root, headers=_auth(a), json=payload).status_code == 409
    assert client.get(root, headers=_auth(b)).json()["enabled"] is False
    moment = [service.now_utc().replace(hour=0, minute=0, second=0, microsecond=0)]
    monkeypatch.setattr(schedule, "now_utc", lambda: moment[0])
    monkeypatch.setattr(discovery, "now_utc", lambda: moment[0])
    calls = []
    def source(**kwargs):
        calls.append(kwargs)
        if len(calls) < 2:
            return {"outcome": "source_unavailable"}
        return {"outcome": "success_empty", "source": "public_eis_html_44fz", "cards": [], "source_coverage_complete": True, "has_more": False}
    monkeypatch.setattr(discovery, "search_public_44fz", source)
    assert schedule.tick(session, settings.model_copy(update={"saas_company_schedule_enabled": False}))["considered"] == 0
    assert not calls
    assert schedule.tick(session, settings)["outcomes"] == {"IN_PROGRESS": 1}
    latest = "/api/saas/company-portfolio/discovery/latest"
    run = client.get(latest, headers=_auth(a)).json()["run"]
    assert run["completed_steps"] == 0 and len(run["attempt_receipts"]) == 1
    assert run["attempt_receipts"][0]["outcome"] == "source_unavailable"
    assert client.get(latest, headers=_auth(b)).json()["run"] is None
    assert schedule.tick(session, settings)["outcomes"] == {"IN_PROGRESS": 1}
    assert len(calls) == 1
    moment[0] += timedelta(minutes=5)
    assert schedule.tick(session, settings)["outcomes"] == {"COMPLETED": 1}
    run = client.get(latest, headers=_auth(a)).json()["run"]
    assert run["completed_steps"] == 1 and len(run["attempt_receipts"]) == 2
    assert schedule.tick(session, settings)["outcomes"] == {"already_finished": 1}
    assert len(calls) == 2
    moment[0] += timedelta(days=1)
    assert client.put("/api/saas/profile", headers=_auth(a), json=profile).status_code == 200
    assert schedule.tick(session, settings)["outcomes"] == {"blocked_409": 1}
    assert len(calls) == 2
    disabled = client.put(root, headers=_auth(a), json={"enabled": False, "expected_revision": 1})
    assert disabled.status_code == 200 and disabled.json()["revision"] == 2
    assert schedule.tick(session, settings)["considered"] == 0
    assert session.query(CompanyDiscoverySchedule).one().tenant_id == tenant["tenant_id"]


def test_company_schedule_retry_budget_and_crash_reservation(client, session, monkeypatch):
    from src.modules.saas_foundation import company_discovery as discovery
    from src.modules.saas_foundation import company_schedule as schedule
    from src.modules.saas_foundation.models import CompanyDiscoveryRun

    _, token = _seed(client, "Расписание авария")
    _legal(client, token)
    profile = _profile()
    profile["criteria"]["regions"] = []
    assert client.put("/api/saas/profile", headers=_auth(token), json=profile).status_code == 200
    settings = saas.get_settings().model_copy(update={"saas_company_discovery_enabled": True, "saas_company_schedule_enabled": True})
    monkeypatch.setattr(saas, "get_settings", lambda: settings)
    payload = {"enabled": True, "expected_revision": 0, "expected_profile_version": 1, "hour_moscow": 0, "confirm_unattended_public_search": True}
    assert client.put("/api/saas/company-portfolio/discovery/schedule", headers=_auth(token), json=payload).status_code == 200
    moment = [service.now_utc().replace(hour=0, minute=0, second=0, microsecond=0)]
    monkeypatch.setattr(schedule, "now_utc", lambda: moment[0])
    monkeypatch.setattr(discovery, "now_utc", lambda: moment[0])
    calls = []
    class SimulatedExit(BaseException):
        pass
    def source(**kwargs):
        calls.append(kwargs)
        if len(calls) == 3:
            raise SimulatedExit()
        return {"outcome": "source_error"}
    monkeypatch.setattr(discovery, "search_public_44fz", source)
    schedule.tick(session, settings)
    moment[0] += timedelta(minutes=5)
    schedule.tick(session, settings)
    moment[0] += timedelta(minutes=15)
    with pytest.raises(SimulatedExit):
        schedule.tick(session, settings)
    session.expire_all()
    row = session.query(CompanyDiscoveryRun).one()
    assert len(row.attempts_json) == 3 and row.attempts_json[-1]["outcome"] == "IN_FLIGHT"
    assert row.results_json == []
    assert schedule.tick(session, settings)["outcomes"] == {"IN_PROGRESS": 1}
    moment[0] += timedelta(minutes=15)
    assert schedule.tick(session, settings)["outcomes"] == {"PARTIAL": 1}
    session.expire_all()
    assert row.results_json[0]["outcome"] == "source_error" and row.attempts_json[-1]["outcome"] == "ABANDONED_AFTER_CRASH"
    assert len(calls) == 3


def test_company_schedule_revalidates_owner_and_entitlement(client, session, monkeypatch):
    from src.modules.saas_foundation import company_discovery as discovery
    from src.modules.saas_foundation import company_schedule as schedule
    from src.modules.saas_foundation.models import SaasMember

    tenant, owner = _seed(client, "Расписание права")
    _legal(client, owner)
    invitation = client.post("/api/saas/invitations", headers=_auth(owner), json={"role": "admin", "acquisition_channel": "referral"}).json()
    admin = client.post("/api/saas/invitations/redeem", json={"invitation_code": invitation["invitation_code"], "display_name": "Fixture administrator"}).json()["access_token"]
    _legal(client, admin)
    settings = saas.get_settings().model_copy(update={"saas_company_discovery_enabled": True, "saas_company_schedule_enabled": True})
    monkeypatch.setattr(saas, "get_settings", lambda: settings)
    assert client.put("/api/saas/profile", headers=_auth(owner), json=_profile()).status_code == 200
    root = "/api/saas/company-portfolio/discovery/schedule"
    body = {"enabled": True, "expected_revision": 0, "expected_profile_version": 1, "hour_moscow": 0, "confirm_unattended_public_search": True}
    assert client.put(root, headers=_auth(admin), json=body).status_code == 403
    assert client.put(root, headers=_auth(owner), json=body).status_code == 200
    calls = []
    monkeypatch.setattr(discovery, "search_public_44fz", lambda **kw: calls.append(kw))
    company = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant["tenant_id"]))
    member = session.scalar(select(SaasMember).where(SaasMember.tenant_id == tenant["tenant_id"], SaasMember.role == "owner"))
    company.trial_ends_at = service.now_utc() - timedelta(days=1)
    session.commit()
    assert schedule.tick(session, settings)["outcomes"] == {"blocked_402": 1}
    company.trial_ends_at = service.now_utc() + timedelta(days=1)
    session.commit()
    member.active = False
    session.commit()
    assert schedule.tick(session, settings)["outcomes"] == {"blocked_403": 1}
    assert not calls


def test_commercial_capture_original_replay_and_scope(client, session, monkeypatch):
    from sqlalchemy import text
    from test_company_commercial_card_evidence import WORKSPACE, workspace

    from src.modules.saas_foundation import commercial_capture as capture
    from src.modules.saas_foundation.models import (
        CommercialCaptureAttempt,
        CommercialCardSnapshot,
    )

    _, a = _seed(client, 'Capture A')
    _, b = _seed(client, 'Capture B')
    _legal(client, a)
    _legal(client, b)
    base = '/api/saas/company-portfolio'
    case = client.post(base+'/commercial-cases', headers=_auth(a), json={'source_url': WORKSPACE}).json()['case_id']
    foreign = client.post(base+'/commercial-cases', headers=_auth(b), json={'source_url': WORKSPACE}).json()['case_id']
    path = f'{base}/cases/{case}/commercial-captures'
    body = {'confirm_public_capture': True}
    calls = []

    def source(url):
        calls.append(url)
        assert session.query(CommercialCaptureAttempt).count() == 1
        assert session.query(CommercialCardSnapshot).count() == 0
        return capture.SourceResponse(url, 'text/html', 200, service.now_utc(), workspace())

    monkeypatch.setattr(capture, 'fetch_card', source)
    assert client.post(path, headers=_auth(a), json=body).status_code == 404
    settings = saas.get_settings().model_copy(update={'saas_commercial_capture_enabled': True})
    monkeypatch.setattr(saas, 'get_settings', lambda: settings)
    assert client.post(path, headers=_auth(a), json={'confirm_public_capture':False}).status_code == 422
    assert client.post(path, headers=_auth(a), json={**body, 'source_url': 'https://evil.invalid'}).status_code == 422
    assert client.post(path, headers=_auth(b), json=body).status_code == 404
    assert not calls
    first = client.post(path, headers=_auth(a), json=body)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['outcome'] == 'CAPTURED' and result['receipt']['external_id'] == '19043'
    assert result['current_live_notice_status_verified'] is False
    assert 'original_html' not in result
    assert client.post(path, headers=_auth(a), json=body).json() == result
    assert calls == [WORKSPACE]
    detail = path+'/'+result['attempt_id']
    assert client.get(detail, headers=_auth(a)).json()['original_reverified'] is True
    assert client.get(detail, headers=_auth(b)).status_code == 404
    assert client.get(f'{base}/cases/{foreign}/commercial-captures/{result["attempt_id"]}', headers=_auth(b)).status_code == 404
    assert client.get(path, headers=_auth(a)).json()['items'] == [result]
    row = session.query(CommercialCardSnapshot).one()
    assert row.original_html == workspace()
    with pytest.raises(ValueError, match='immutable'):
        row.original_html = b'changed'
        session.flush()
    session.rollback()
    session.execute(text('UPDATE commercial_card_snapshots SET original_html=:raw'), {'raw':workspace()+b' '})
    session.commit()
    assert client.get(detail, headers=_auth(a)).status_code == 409
    assert calls == [WORKSPACE]


def test_commercial_capture_failed_and_crash_reservations_are_not_retried(client, session, monkeypatch):
    from src.modules.saas_foundation import commercial_capture as capture
    from src.modules.saas_foundation.models import (
        CommercialCaptureAttempt,
        CommercialCardSnapshot,
    )

    _, a = _seed(client, 'Capture retries')
    _legal(client, a)
    settings = saas.get_settings().model_copy(update={'saas_commercial_capture_enabled': True})
    monkeypatch.setattr(saas, 'get_settings', lambda: settings)
    monkeypatch.setattr(capture, 'MAX_DAILY_PER_TENANT', 3)
    base = '/api/saas/company-portfolio'
    paths = []
    for i in range(4):
        url = f'https://workspace.ru/tenders/fixture-{19043+i}/'
        saved = client.post(base+'/commercial-cases', headers=_auth(a), json={'source_url':url})
        assert saved.status_code == 201
        paths.append(f'{base}/cases/{saved.json()["case_id"]}/commercial-captures')
    calls = []

    class Crash(BaseException):
        pass

    def source(url):
        calls.append(url)
        if len(calls)==1:
            raise ValueError('unavailable')
        if len(calls)==2:
            return capture.SourceResponse(url, 'text/html', 200, service.now_utc(), b'<html><body>login</body></html>')
        raise Crash()

    monkeypatch.setattr(capture, 'fetch_card', source)
    body = {'confirm_public_capture':True}
    for path, outcome in zip(paths, ('SOURCE_UNAVAILABLE','UNSUPPORTED_CARD'), strict=False):
        first = client.post(path, headers=_auth(a), json=body).json()
        assert first['outcome'] == outcome and first['receipt'] is None
        assert client.post(path, headers=_auth(a), json=body).json() == first
    # Simulate process interruption at the service boundary, not the ASGI event loop.
    principal = service.require_tenant(session, a)
    with pytest.raises(Crash):
        capture.capture(session, principal, paths[2].split("/")[-2], capture.CaptureRequest(**body))
    session.rollback()
    session.expire_all()
    assert client.post(paths[2], headers=_auth(a), json=body).json()['outcome'] == 'UNCONFIRMED_ATTEMPT'
    assert client.post(paths[3], headers=_auth(a), json=body).status_code == 429
    assert len(calls)==3 and session.query(CommercialCaptureAttempt).count()==3
    assert all(x.original_html is None and x.receipt_json is None for x in session.query(CommercialCardSnapshot).all())


def test_commercial_capture_historical_comparison(client, session, monkeypatch):
    from test_company_commercial_card_evidence import WORKSPACE, workspace

    from src.modules.saas_foundation import commercial_capture as capture

    _, a = _seed(client, 'Capture comparison')
    _, b = _seed(client, 'Foreign comparison')
    _legal(client, a)
    _legal(client, b)
    settings = saas.get_settings().model_copy(update={'saas_commercial_capture_enabled': True})
    monkeypatch.setattr(saas, 'get_settings', lambda: settings)
    moment = [service.now_utc()]
    monkeypatch.setattr(capture, 'now_utc', lambda: moment[0])
    base = '/api/saas/company-portfolio'
    def path(token, url):
        case = client.post(base+'/commercial-cases', headers=_auth(token), json={'source_url':url})
        assert case.status_code == 201
        return f'{base}/cases/{case.json()["case_id"]}/commercial-captures'
    route, foreign = path(a, WORKSPACE), path(b, WORKSPACE)
    calls = []
    raw = [workspace().replace(b'</body>',b'<a href="/docs/old.pdf">old</a></body>')]
    def source(url):
        calls.append(url)
        return capture.SourceResponse(url,'text/html',200,moment[0],raw[0])
    monkeypatch.setattr(capture,'fetch_card',source)
    def save(token, route):
        r = client.post(route, headers=_auth(token), json={'confirm_public_capture':True})
        assert r.status_code == 201, r.text
        return r.json()['attempt_id']
    older = save(a,route)
    outsider = save(b,foreign)
    moment[0] += timedelta(days=1)
    raw[0] = workspace(stage='Завершён',deadline='29 октября 2026').replace(b'</body>',b'<a href="/docs/new.pdf">new</a></body>')
    newer = save(a,route)
    r = client.get(route+'/'+newer,headers=_auth(a),params={'previous_attempt_id':older})
    assert r.status_code == 200,r.text
    comp = r.json()['comparison']
    assert comp['html_changed'] and comp['observed_field_changes']['displayed_deadline']['after']=='2026-10-29'
    assert comp['observed_field_changes']['displayed_stage']['after']=='Завершён'
    assert [x['source_url'] for x in comp['candidate_links_added']]==['https://workspace.ru/docs/new.pdf']
    assert [x['source_url'] for x in comp['candidate_links_absent']]==['https://workspace.ru/docs/old.pdf']
    assert not comp['attachment_bytes_compared'] and not comp['candidate_link_coverage_complete']
    assert client.get(route+'/'+newer,headers=_auth(a),params={'previous_attempt_id':outsider}).status_code==404
    assert client.get(route+'/'+older,headers=_auth(a),params={'previous_attempt_id':newer}).status_code==422
    assert client.get(route+'/'+newer,headers=_auth(a),params={'previous_attempt_id':newer}).status_code==422
    assert len(calls)==3


def test_commercial_attachment_intake_provenance_replay_revision_and_isolation(client, session, monkeypatch):
    from hashlib import sha256

    from sqlalchemy import text
    from test_commercial_attachment_bytes import docx_fixture
    from test_company_commercial_card_evidence import WORKSPACE, workspace

    from src.modules.saas_foundation import commercial_capture as capture
    from src.modules.saas_foundation.models import CommercialAttachmentEvidence

    _, a = _seed(client, 'Attachments A')
    _, b = _seed(client, 'Attachments B')
    _legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_commercial_capture_enabled':True})
    monkeypatch.setattr(saas,'get_settings',lambda:settings)
    moment=[service.now_utc()];monkeypatch.setattr(capture,'now_utc',lambda:moment[0]);calls=[]
    card=workspace().replace(b'</body>',b'<a href="/docs/spec.docx">spec</a></body>')
    def fetch(url):
        calls.append(url);return capture.SourceResponse(url,'text/html',200,moment[0],card)
    monkeypatch.setattr(capture,'fetch_card',fetch)
    base='/api/saas/company-portfolio'
    def case_path(token):
        row=client.post(base+'/commercial-cases',headers=_auth(token),json={'source_url':WORKSPACE});assert row.status_code==201
        return f'{base}/cases/{row.json()["case_id"]}/commercial-captures'
    route,foreign=case_path(a),case_path(b)
    def capture_path(token,path):
        r=client.post(path,headers=_auth(token),json={'confirm_public_capture':True});assert r.status_code==201,r.text
        return path+'/'+r.json()['attempt_id']
    old=capture_path(a,route);other=capture_path(b,foreign)
    record=client.get(old,headers=_auth(a)).json();candidate=record['attachment_inventory']['candidates'][0]['candidate_id'];assert candidate==sha256(b'https://workspace.ru/docs/spec.docx').hexdigest()
    attach=lambda path:path+'/attachments/'+candidate
    body=docx_fixture();params={'confirm_user_supplied':True}
    assert client.post(attach(old),headers=_auth(a),params=params,content=body).status_code==404
    settings=settings.model_copy(update={'saas_commercial_attachment_intake_enabled':True})
    assert client.post(attach(old),headers=_auth(a),content=body).status_code==422
    assert client.post(attach(old),headers=_auth(b),params=params,content=body).status_code==404
    assert client.post(old+'/attachments/'+'f'*64,headers=_auth(a),params=params,content=body).status_code==404
    assert client.post(attach(old),headers=_auth(a),params=params,content=b'<html>wrong</html>').status_code==422
    assert client.post(attach(old),headers=_auth(a),params=params,content=b'x'*(2*1024*1024+1)).status_code==413
    r=client.post(attach(old),headers=_auth(a),params=params,content=body);assert r.status_code==201,r.text
    evidence=r.json();assert evidence['origin']=='USER_SUPPLIED_UNATTESTED' and evidence['stored_bytes_reverified'] and not evidence['platform_original_verified']
    assert client.post(attach(old),headers=_auth(a),params=params,content=body).json()==evidence
    assert client.post(attach(old),headers=_auth(a),params=params,content=docx_fixture('changed')).status_code==409
    assert client.get(old+'/attachments',headers=_auth(a)).json()['items'][0]['inspection'].get('text_preview') is None
    assert client.get(attach(old),headers=_auth(b)).status_code==404
    assert client.get(attach(other),headers=_auth(b)).status_code==404
    text_path=attach(old)+'/text-evidence'
    assert client.get(text_path,headers=_auth(a)).status_code==404
    settings=settings.model_copy(update={'saas_commercial_text_projection_enabled':True})
    projected=client.get(text_path,headers=_auth(a));assert projected.status_code==200,projected.text
    result=projected.json();assert result['text_projection']['source_sha256']==result['inspection']['sha256']
    assert result['text_projection']['fragments'][0]['text']=='Поставка и монтаж оборудования'
    assert result['supplier_profile_context']['profile_state']=='MISSING' and not result['supplier_profile_context']['requirements_compared']
    assert client.get(text_path,headers=_auth(b)).status_code==404

    moment[0]+=timedelta(days=1);new=capture_path(a,route)
    r=client.post(attach(new),headers=_auth(a),params=params,content=docx_fixture('Новая редакция'));assert r.status_code==201,r.text
    previous=old.split('/')[-1];r=client.get(attach(new),headers=_auth(a),params={'previous_attempt_id':previous});assert r.status_code==200,r.text
    assert r.json()['comparison']['supplied_bytes_changed'] and not r.json()['comparison']['platform_document_version_verified']
    assert client.get(attach(new),headers=_auth(a),params={'previous_attempt_id':other.split('/')[-1]}).status_code==404
    assert len(calls)==3 and session.query(CommercialAttachmentEvidence).count()==2
    row=session.query(CommercialAttachmentEvidence).filter_by(id=evidence['evidence_id']).one();assert row.raw_bytes==body
    session.execute(text('UPDATE commercial_attachment_evidence SET raw_bytes=:raw WHERE id=:id'),{'raw':docx_fixture('tampered'),'id':row.id});session.commit()
    assert client.get(attach(old),headers=_auth(a)).status_code==409


def test_requirement_review_matrix_versions_scope_and_replay(client, session, monkeypatch):
    from test_commercial_attachment_bytes import docx_fixture
    from test_company_commercial_card_evidence import WORKSPACE, workspace

    from src.modules.saas_foundation import commercial_capture as capture
    from src.modules.saas_foundation.models import CommercialRequirementReview

    _, a = _seed(client,'Requirement A'); _, b = _seed(client,'Requirement B')
    for token in (a,b):
        _legal(client,token)
        assert client.put('/api/saas/profile',headers=_auth(token),json=_profile()).status_code==200
    settings=saas.get_settings().model_copy(update={'saas_commercial_capture_enabled':True,'saas_commercial_attachment_intake_enabled':True})
    monkeypatch.setattr(saas,'get_settings',lambda:settings)
    card=workspace().replace(b'</body>',b'<a href="/docs/spec.docx">spec</a><a href="/docs/contract.docx">contract</a><a href="/docs/missing.pdf">missing</a><a href="/docs/other.pdf">other</a></body>')
    monkeypatch.setattr(capture,'fetch_card',lambda url:capture.SourceResponse(url,'text/html',200,service.now_utc(),card))
    def setup(token):
        base='/api/saas/company-portfolio'
        case=client.post(base+'/commercial-cases',headers=_auth(token),json={'source_url':WORKSPACE}).json()['case_id']
        cap=f'{base}/cases/{case}/commercial-captures';attempt=client.post(cap,headers=_auth(token),json={'confirm_public_capture':True}).json()['attempt_id']
        parent=cap+'/'+attempt;candidate=client.get(parent,headers=_auth(token)).json()['attachment_inventory']['candidates'][0]['candidate_id']
        path=parent+'/attachments/'+candidate
        assert client.post(path,headers=_auth(token),params={'confirm_user_supplied':True},content=docx_fixture('Поставщик должен иметь опыт поставки')).status_code==201
        return path+'/requirements'
    route,foreign=setup(a),setup(b)
    case_route=route.split('/attachments/')[0]+'/requirement-matrix'
    parent=route.split('/attachments/')[0]
    candidates=client.get(parent,headers=_auth(a)).json()['attachment_inventory']['candidates']
    second=parent+'/attachments/'+candidates[1]['candidate_id']
    assert client.post(second,headers=_auth(a),params={'confirm_user_supplied':True},content=docx_fixture('Срок поставки 30 дней')).status_code==201
    fourth=parent+'/attachments/'+candidates[3]['candidate_id']
    assert client.post(fourth,headers=_auth(a),params={'confirm_user_supplied':True},content=b'%PDF-1.4\nfixture\n%%EOF').status_code==201
    assert client.get(case_route,headers=_auth(a)).status_code==404

    assert client.get(route,headers=_auth(a)).status_code==404
    settings=settings.model_copy(update={'saas_commercial_requirement_review_enabled':True})
    def reference(token,version=0):
        r=client.post('/api/saas/qualification/references',headers=_auth(token),json={'expected_version':version,'source_ref':'fixture','snapshot':{'schema_version':'completed-contract-references-v1','as_of_date':'2026-11-16','completeness':'PARTIAL','owner_confirmed':False,'contracts':[]}})
        assert r.status_code==201,r.text;return r.json()['fact_id']
    ref,other_ref=reference(a),reference(b)
    for token in (a,b):
        r=client.post('/api/saas/documents',headers=_auth(token),data={'document_key':'license_fixture','document_type':'LICENSE','display_name':'Fixture'},files={'file':('fixture.pdf',b'%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF','application/pdf')});assert r.status_code==201,r.text
    first=client.get(route,headers=_auth(a));assert first.status_code==200,first.text
    combined=client.get(case_route,headers=_auth(a));assert combined.status_code==200,combined.text
    aggregate=combined.json();assert aggregate['candidate_count']==4 and aggregate['stored_copy_count']==3 and aggregate['missing_copy_count']==1
    assert aggregate['page_summary']['unreviewed']==2 and aggregate['has_more'] and not aggregate['coverage_complete']
    assert [d['state'] for d in aggregate['documents']]==['PARTIAL_REVIEW_CANDIDATES','PARTIAL_REVIEW_CANDIDATES','MISSING_USER_COPY']
    assert client.get(case_route,headers=_auth(b)).status_code==404
    page=client.get(case_route,headers=_auth(a),params={'offset':3}).json();assert not page['has_more'] and page['documents'][0]['state']=='REVIEW_FORMAT_UNSUPPORTED'
    assert client.get(case_route,headers=_auth(a),params={'limit':4}).status_code==422
    matrix=first.json();foreign_matrix=client.get(foreign,headers=_auth(b)).json();item=matrix['items'][0];key=item['fragment_key'];doc=matrix['document_options'][0]['document_version_id']
    assert matrix['summary']['unreviewed']==1 and matrix['reference_list']['fact_id']==ref
    body={'fragment_key':key,'profile_fact_id':matrix['profile']['fact_id'],'expected_revision':0,'assessment':'HUMAN_SUPPORT_RECORDED','reference_fact_id':ref,'document_version_id':doc,'rationale':'Human review fixture, not qualification proof','idempotency_key':'review-first'}
    assert client.get(route,headers=_auth(b)).status_code==404
    assert client.post(route,headers=_auth(a),json={**body,'reference_fact_id':other_ref}).status_code==409
    assert client.post(route,headers=_auth(a),json={**body,'document_version_id':foreign_matrix['document_options'][0]['document_version_id']}).status_code==409
    assert client.post(route,headers=_auth(a),json={**body,'reference_fact_id':None,'document_version_id':None}).status_code==422
    r=client.post(route,headers=_auth(a),json=body);assert r.status_code==201,r.text
    saved=r.json();assert saved['revision']==1 and not saved['qualification_verified'] and not saved['stale_reasons']
    assert client.post(route,headers=_auth(a),json=body).json()==saved
    assert client.post(route,headers=_auth(a),json={**body,'rationale':'different'}).status_code==409
    assert client.post(route,headers=_auth(a),json={**body,'idempotency_key':'review-second'}).status_code==409
    assert client.put('/api/saas/profile',headers=_auth(a),json=_profile()).status_code==200
    newref=reference(a,1)
    # Synthetic metadata for a new document version: this test does not assert artifact bytes.
    from src.modules.company_profile_store.models import CompanyDocumentVersion
    old_doc=session.get(CompanyDocumentVersion,doc)
    session.add(CompanyDocumentVersion(company_document_id=old_doc.company_document_id,version_no=2,artifact_version_no=2,source_type='CUSTOMER_PROVIDED',source_ref='fixture-new-version'))
    session.commit()
    new=client.get(route,headers=_auth(a)).json();review=new['items'][0]['review'];assert set(review['stale_reasons'])=={'PROFILE_CHANGED_OR_INACTIVE','REFERENCE_LIST_CHANGED_OR_INACTIVE','DOCUMENT_CHANGED_OR_INACTIVE'}
    assert new['summary']['needs_evidence']==1
    combined=client.get(case_route,headers=_auth(a)).json();assert combined['page_summary']['needs_evidence']==1 and combined['page_summary']['unreviewed']==1
    updated={**body,'profile_fact_id':new['profile']['fact_id'],'reference_fact_id':newref,'expected_revision':1,'idempotency_key':'review-second','assessment':'NEEDS_EVIDENCE','document_version_id':None}
    r=client.post(route,headers=_auth(a),json=updated);assert r.status_code==201,r.text
    h=client.get(route+'/'+key,headers=_auth(a)).json();assert [x['revision'] for x in h['items']]==[2,1]
    assert session.query(CommercialRequirementReview).count()==2
    assert client.get(route+'/'+key,headers=_auth(b)).status_code==404
    assert not client.get(foreign,headers=_auth(b)).json()['items'][0]['review']


def test_company_manager_inbox_due_and_latest_decision_scope(client, session, monkeypatch):
    from src.modules.saas_foundation import company_portfolio as portfolio
    from src.modules.saas_foundation.models import CompanyPortfolioDecision

    _, owner = _seed(client, 'Manager inbox A')
    _, other = _seed(client, 'Manager inbox B')
    route = '/api/saas/company-portfolio/manager-inbox'
    cases = '/api/saas/company-portfolio/cases'
    assert client.get(route, headers=_auth(owner)).status_code == 428
    _legal(client, owner); _legal(client, other)
    moment = [service.now_utc()]
    monkeypatch.setattr(portfolio, 'now_utc', lambda: moment[0])
    def save(token, number):
        r = client.post(cases, headers=_auth(token), json={'registry_number': number})
        assert r.status_code == 201, r.text
        return r.json()['case_id']
    def decision(case_id, action, rev, until=None):
        r = client.post(f'{cases}/{case_id}/decisions', headers=_auth(owner), json={'action':action, 'expected_revision':rev, 'rationale':'Fixture only', 'idempotency_key':f'inbox-fixture-{rev+1}', 'deferred_until':until.isoformat() if until else None})
        assert r.status_code == 200,r.text
    ids = [save(owner, f'{i+1:019d}') for i in range(5)]
    foreign = save(other, '0000000000000000001')
    commercial = client.post('/api/saas/company-portfolio/commercial-cases', headers=_auth(owner), json={'source_url':'https://workspace.ru/tenders/fixture-19019/'}).json()['case_id']
    decision(ids[1], 'DEFER', 0, moment[0]+timedelta(hours=1))
    decision(ids[2], 'DEFER', 0, moment[0]+timedelta(days=2))
    decision(ids[3], 'DEFER', 0, moment[0]+timedelta(hours=1))
    decision(ids[3], 'GO', 1)
    decision(ids[4], 'NO_GO', 0)
    moment[0] += timedelta(hours=1)
    first = client.get(route, headers=_auth(owner), params={'limit':1})
    assert first.status_code == 200, first.text
    data = first.json()
    assert data['summary'] == {'undecided':2,'deferred_due':1,'deferred_future':1,'go':1,'no_go':1,'attention':3,'all':6}
    assert data['items'][0]['case_id']==ids[1] and data['items'][0]['inbox_state']=='deferred_due' and data['has_more']
    later = client.get(route, headers=_auth(owner), params={'offset':1,'limit':2}).json()
    assert {x['case_id'] for x in later['items']}=={ids[0],commercial} and not later['has_more']
    assert not data['external_submission_allowed'] and not data['live_deadline_verified'] and not data['market_coverage_complete']
    for view, expected in [('go',ids[3]),('no_go',ids[4]),('deferred_future',ids[2]),('deferred_due',ids[1])]:
        r=client.get(route,headers=_auth(owner),params={'view':view}).json()
        assert [x['case_id'] for x in r['items']]==[expected] and r['summary']==data['summary']
    assert client.get(route,headers=_auth(other)).json()['items'][0]['case_id']==foreign
    assert client.get(route,headers=_auth(other)).json()['summary']['all']==1
    assert client.get(route,headers=_auth(owner),params={'view':'won'}).status_code==422
    assert session.query(CompanyPortfolioDecision).count()==5
    invite=client.post('/api/saas/invitations',headers=_auth(owner),json={'role':'viewer','acquisition_channel':'referral'}).json()
    viewer=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':'viewer'}).json()['access_token']
    _legal(client,viewer)
    assert client.get(route,headers=_auth(viewer)).json()['summary']==data['summary']
    decision(ids[1],'GO',1)
    updated=client.get(route,headers=_auth(owner)).json()
    assert updated['summary']['attention']==2 and updated['summary']['go']==2 and updated['summary']['deferred_due']==0


def test_company_lifecycle_attestation_and_metrics(client, session, monkeypatch):
    from src.modules.saas_foundation.models import CompanyCaseLifecycleEvent

    _, a = _seed(client,'Lifecycle A'); _, b = _seed(client,'Lifecycle B')
    _legal(client,a); _legal(client,b)
    base='/api/saas/company-portfolio';cases=base+'/cases';metrics=base+'/lifecycle-metrics'
    settings=saas.get_settings()
    monkeypatch.setattr(saas,'get_settings',lambda:settings)
    def save(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']
    path,foreign,second,third=[save(token,n) for token,n in ((a,1),(b,1),(a,2),(a,3))]
    assert client.get(path+'/lifecycle',headers=_auth(a)).status_code==404
    settings=settings.model_copy(update={'saas_company_lifecycle_enabled':True})
    def decide(path,rev,action='GO'):
        r=client.post(path+'/decisions',headers=_auth(a),json={'action':action,'expected_revision':rev,'rationale':'fixture','idempotency_key':f'decision-{rev}'});assert r.status_code==200,r.text
    def event(path,stage,rev,decision_rev=1,**extra):
        body={'stage':stage,'expected_revision':rev,'expected_decision_revision':decision_rev,'rationale':'fixture','idempotency_key':f'lifecycle-{rev}',**extra}
        return client.post(path+'/lifecycle',headers=_auth(a),json=body)
    now=service.now_utc();receipt={'source_ref':'receipt 123','occurred_at':(now-timedelta(minutes=2)).isoformat()};outcome={'source_ref':'protocol 123','occurred_at':now.isoformat()}
    assert event(path,'READY',0).status_code==409
    for p in (path,second,third):decide(p,0)
    assert event(path,'SUBMITTED',0,**receipt).status_code==409
    r=event(path,'READY',0);assert r.status_code==201,r.text
    assert event(path,'READY',0).json()==r.json()
    decide(path,1,'NO_GO');assert client.get(path+'/lifecycle',headers=_auth(a)).json()['latest']['readiness_stale']
    decide(path,2);assert event(path,'SUBMITTED',1,3,**receipt).status_code==409
    assert event(path,'READY',1,3).status_code==201
    assert event(path,'SUBMITTED',2,3).status_code==422
    r=event(path,'SUBMITTED',2,3,**receipt);assert r.status_code==201,r.text
    assert r.json()['origin']=='HUMAN_ATTESTATION' and not r.json()['external_fact_verified']
    assert event(path,'WON',3,3,source_ref='protocol',occurred_at=(now-timedelta(days=1)).isoformat()).status_code==422
    assert event(path,'WON',3,3,**outcome).status_code==201
    assert event(path,'LOST',4,3,**outcome).status_code==409
    assert event(path,'LOST',4,3,correct_outcome=True,**outcome).status_code==201
    assert event(path,'WON',5,3,correct_outcome=True,**outcome).status_code==201
    assert event(path,'SUBMITTED',6,3,**receipt).status_code==409
    assert event(second,'READY',0).status_code==201
    assert event(second,'SUBMITTED',1,**receipt).status_code==201
    assert event(second,'REJECTED',2,**outcome).status_code==201
    h=client.get(path+'/lifecycle/history',headers=_auth(a)).json();assert [x['revision'] for x in h['items']]==[6,5,4,3,2,1]
    assert client.get(path+'/lifecycle',headers=_auth(b)).status_code==404
    assert event(foreign,'READY',0).status_code==404
    m=client.get(metrics,headers=_auth(a));assert m.status_code==200,m.text
    m=m.json();assert m['saved_cases']==3 and m['ever_go_cases']==3 and m['recorded_submissions']==2
    assert m['win_rate']=={'numerator':1,'denominator':2,'rate':0.5}
    assert m['go_to_submission']['numerator']==2 and m['go_to_submission']['denominator']==3
    assert not m['external_facts_verified'] and not m['contract_revenue_verified']
    other=client.get(metrics,headers=_auth(b)).json();assert other['saved_cases']==1 and other['win_rate']['rate'] is None and other['go_to_submission']['rate'] is None
    assert session.query(CompanyCaseLifecycleEvent).count()==9


def test_versioned_readiness_binding_and_submission_gate(client, session, monkeypatch):
    from test_commercial_attachment_bytes import docx_fixture
    from test_company_commercial_card_evidence import WORKSPACE, workspace

    from src.modules.saas_foundation import commercial_capture as capture
    from src.modules.saas_foundation.models import CompanyReadinessEvidence

    _, a=_seed(client,'Readiness A'); _, b=_seed(client,'Readiness B')
    for token in (a,b):
        _legal(client,token)
        assert client.put('/api/saas/profile',headers=_auth(token),json=_profile()).status_code==200
    settings=saas.get_settings().model_copy(update={'saas_commercial_capture_enabled':True,'saas_commercial_attachment_intake_enabled':True,'saas_commercial_requirement_review_enabled':True,'saas_company_lifecycle_enabled':True})
    monkeypatch.setattr(saas,'get_settings',lambda:settings)
    card=workspace().replace(b'</body>',b'<a href="/docs/spec.docx">spec</a></body>')
    monkeypatch.setattr(capture,'fetch_card',lambda url:capture.SourceResponse(url,'text/html',200,service.now_utc(),card))
    base='/api/saas/company-portfolio';headers=_auth(a)
    case=client.post(base+'/commercial-cases',headers=headers,json={'source_url':WORKSPACE}).json()['case_id'];path=base+'/cases/'+case
    cap=path+'/commercial-captures';attempt=client.post(cap,headers=headers,json={'confirm_public_capture':True}).json()['attempt_id']
    parent=cap+'/'+attempt;candidate=client.get(parent,headers=headers).json()['attachment_inventory']['candidates'][0]['candidate_id'];attach=parent+'/attachments/'+candidate
    assert client.post(attach,headers=headers,params={'confirm_user_supplied':True},content=docx_fixture('Поставщик должен иметь опыт поставки')).status_code==201
    assert client.post(path+'/decisions',headers=headers,json={'action':'GO','expected_revision':0,'rationale':'fixture','idempotency_key':'go-fixture'}).status_code==200
    def event(stage,revision,**extra):
        return client.post(path+'/lifecycle',headers=headers,json={'stage':stage,'expected_revision':revision,'expected_decision_revision':1,'rationale':'fixture','idempotency_key':f'readiness-event-{revision}',**extra})
    assert event('READY',0).status_code==201
    endpoint=path+'/readiness-evidence';assert client.get(endpoint,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_readiness_evidence_enabled':True,'saas_company_commercial_readiness_required':True})
    r=client.get(endpoint,headers=headers);assert r.status_code==200,r.text
    pending=r.json();assert 'UNREVIEWED_FRAGMENT' in pending['projection']['issues'] and not pending['binding_current']
    def bind(state,**extras):
        return client.post(endpoint,headers=headers,json={'ready_event_id':state['ready_event_id'],'projection_sha256':state['projection_sha256'],'acknowledge_partial_coverage':True,**extras})
    assert bind(pending).status_code==409
    receipt={'source_ref':'receipt fixture','occurred_at':service.now_utc().isoformat()}
    assert event('SUBMITTED',1,**receipt).status_code==409
    ref=client.post('/api/saas/qualification/references',headers=headers,json={'expected_version':0,'source_ref':'fixture','snapshot':{'schema_version':'completed-contract-references-v1','as_of_date':'2026-11-16','completeness':'PARTIAL','owner_confirmed':False,'contracts':[]}}).json()['fact_id']
    route=attach+'/requirements'
    uploaded=client.post('/api/saas/documents',headers=headers,data={'document_key':'license_fixture','document_type':'LICENSE','display_name':'Fixture'},files={'file':('fixture.pdf',b'%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF','application/pdf')});assert uploaded.status_code==201,uploaded.text
    def review_body(rev,key):
        matrix=client.get(route,headers=headers).json();frag=matrix['items'][0]
        return {'fragment_key':frag['fragment_key'],'profile_fact_id':matrix['profile']['fact_id'],'expected_revision':rev,'assessment':'HUMAN_SUPPORT_RECORDED','reference_fact_id':ref,'document_version_id':matrix['document_options'][0]['document_version_id'],'rationale':'manual support fixture','idempotency_key':key}
    assert client.post(route,headers=headers,json=review_body(0,'review-fixture-one')).status_code==201
    first=client.get(endpoint,headers=headers).json();assert first['projection']['partial_review_resolved'] and not first['projection']['coverage_complete']
    assert bind(first,acknowledge_partial_coverage=False).status_code==422
    r=bind(first);assert r.status_code==201,r.text
    saved=r.json();assert saved['binding_current'] and not saved['qualification_verified']
    assert bind(first).json()['binding_id']==saved['binding_id']
    assert client.get(endpoint,headers=_auth(b)).status_code==404
    assert client.put('/api/saas/profile',headers=headers,json=_profile()).status_code==200
    stale=client.get(endpoint,headers=headers).json();assert stale['binding_current'] is False and 'STALE_REVIEW' in stale['projection']['issues']
    assert event('SUBMITTED',1,**receipt).status_code==409
    assert client.post(route,headers=headers,json=review_body(1,'review-fixture-two')).status_code==201
    refreshed=client.get(endpoint,headers=headers).json();assert refreshed['projection']['partial_review_resolved'] and not refreshed['binding_current']
    assert bind(refreshed).status_code==409
    assert event('READY',1).status_code==201
    renewed=client.get(endpoint,headers=headers).json();assert renewed['ready_event_id']!=first['ready_event_id']
    assert bind(renewed).status_code==201
    from src.modules.company_profile_store.models import CompanyDocumentVersion
    old_doc=session.get(CompanyDocumentVersion,review_body(2,'unused')['document_version_id'])
    session.add(CompanyDocumentVersion(company_document_id=old_doc.company_document_id,version_no=2,artifact_version_no=2,source_type='CUSTOMER_PROVIDED',source_ref='fixture-new-version'))
    session.commit()
    assert 'STALE_REVIEW' in client.get(endpoint,headers=headers).json()['projection']['issues']
    assert event('SUBMITTED',2,**receipt).status_code==409
    assert client.post(route,headers=headers,json=review_body(2,'review-fixture-three')).status_code==201
    assert event('READY',2).status_code==201
    assert bind(client.get(endpoint,headers=headers).json()).status_code==201
    assert event('SUBMITTED',3,**receipt).status_code==201
    assert session.query(CompanyReadinessEvidence).count()==3


def test_lifecycle_artifact_bytes_scope_and_immutability(client, session, monkeypatch):
    import hashlib

    from src.modules.saas_foundation.models import CompanyLifecycleArtifact

    _, a=_seed(client,'Artifact A'); _, b=_seed(client,'Artifact B')
    _legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_company_lifecycle_enabled':True})
    monkeypatch.setattr(saas,'get_settings',lambda:settings)
    cases='/api/saas/company-portfolio/cases'; headers=_auth(a)
    def save(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']
    path=save(a,1); other=save(b,1); same_tenant=save(a,2)
    assert client.post(path+'/decisions',headers=headers,json={'action':'GO','expected_revision':0,'rationale':'fixture','idempotency_key':'artifact-go'}).status_code==200
    now=service.now_utc().isoformat()
    def event(stage,rev,**extra):
        r=client.post(path+'/lifecycle',headers=headers,json={'stage':stage,'expected_revision':rev,'expected_decision_revision':1,'rationale':'fixture','idempotency_key':f'artifact-event-{rev}',**extra});assert r.status_code==201,r.text
        return r.json()['event_id']
    ready=event('READY',0);submitted=event('SUBMITTED',1,source_ref='receipt fixture',occurred_at=now);won=event('WON',2,source_ref='protocol fixture',occurred_at=now)
    url=path+'/lifecycle/'+submitted+'/artifact';protocol=path+'/lifecycle/'+won+'/artifact'
    raw=b'%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF';params={'format_hint':'pdf','confirm_user_supplied':True}
    assert client.get(url,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_lifecycle_artifacts_enabled':True})
    assert client.get(url,headers=headers).status_code==404
    assert client.post(url,headers=headers,params={'format_hint':'pdf'},content=raw).status_code==422
    assert client.post(url,headers=headers,params=params,content=b'not pdf').status_code==422
    assert client.post(url,headers=headers,params=params,content=b'x'*(2*1024*1024+1)).status_code==413
    assert client.post(path+'/lifecycle/'+ready+'/artifact',headers=headers,params=params,content=raw).status_code==409
    assert client.post(url,headers=_auth(b),params=params,content=raw).status_code==404
    assert client.post(same_tenant+'/lifecycle/'+submitted+'/artifact',headers=headers,params=params,content=raw).status_code==404
    assert client.post(other+'/lifecycle/'+submitted+'/artifact',headers=_auth(b),params=params,content=raw).status_code==404
    response=client.post(url,headers=headers,params=params,content=raw);assert response.status_code==201,response.text
    first=response.json();sha=hashlib.sha256(raw).hexdigest();assert first['inspection']['sha256']==sha and first['artifact_kind']=='SUBMISSION_RECEIPT'
    assert first['stored_bytes_reverified'] and not first['external_fact_verified'] and not first['platform_original_verified']
    assert client.post(url,headers=headers,params=params,content=raw).json()==first
    assert client.post(url,headers=headers,params=params,content=raw.replace(b'1 0 obj',b'2 0 obj')).status_code==409
    assert client.get(url,headers=headers).json()==first
    invite=client.post('/api/saas/invitations',headers=headers,json={'role':'viewer','acquisition_channel':'referral'}).json()
    viewer=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':'viewer'}).json()['access_token']
    _legal(client,viewer)
    assert client.get(url,headers=_auth(viewer)).json()==first
    assert client.get(url+'/download',headers=_auth(viewer)).content==raw
    assert client.post(protocol,headers=_auth(viewer),params=params,content=raw).status_code==403
    assert client.get(url+'/download',headers=_auth(b)).status_code==404
    dl=client.get(url+'/download',headers=headers);assert dl.status_code==200 and dl.content==raw
    assert dl.headers['x-artifact-sha256']==sha and dl.headers['cache-control']=='private, no-store' and 'attachment;' in dl.headers['content-disposition']
    r=client.post(protocol,headers=headers,params=params,content=raw);assert r.status_code==201 and r.json()['artifact_kind']=='OUTCOME_PROTOCOL'
    assert session.query(CompanyLifecycleArtifact).count()==2
    # Corruption simulation via SQL in the isolated fixture, not via the immutable ORM.
    from sqlalchemy import update
    session.execute(update(CompanyLifecycleArtifact).where(CompanyLifecycleArtifact.id==first['artifact_id']).values(raw_bytes=raw.replace(b'1 0 obj',b'9 0 obj')));session.commit()
    assert client.get(url,headers=headers).status_code==409
    assert client.get(url+'/download',headers=headers).status_code==409


def test_company_price_scenarios_exact_economics_and_scope(client, session, monkeypatch):
    from src.modules.saas_foundation.models import CompanyPriceScenario

    _, a=_seed(client,'PRICE A'); _, b=_seed(client,'PRICE B')
    _legal(client,a);_legal(client,b)
    settings=saas.get_settings();monkeypatch.setattr(saas,'get_settings',lambda:settings)
    cases='/api/saas/company-portfolio/cases';headers=_auth(a)
    def create(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']+'/price-scenarios'
    path=create(a,1);foreign=create(b,1);same=create(a,2)
    assert client.get(path,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_price_scenarios_enabled':True})
    inputs={'external_direct_rub':'60000','own_labor_rub':'20000','cash_overhead_rub':'10000','reserve_rub':'5000','fixed_platform_fees_rub':'2000','guarantee_financing_cost_rub':'3000','revenue_tax_percent':'6','variable_platform_fee_percent':'4','minimum_profit_rub':'5000','target_profit_rub':'20000','reference_ceiling_rub':'120000','manual_bid_prices_rub':['80000','100000','120000'],'assumption_note':'Synthetic test only, explicit revenue-based shares, reserve and guarantee cost','accept_hypothetical_assumptions_only':True}
    def preview(body,token=a,url=path):return client.post(url+'/preview',headers=_auth(token),json=body)
    def save(body,rev=0,key='price-fixture-1',url=path,token=a):return client.post(url,headers=_auth(token),json={'scenario':body,'expected_revision':rev,'idempotency_key':key})
    r=preview(inputs);assert r.status_code==200,r.text
    result=r.json()['result'];assert not r.json()['inputs_stored'] and session.query(CompanyPriceScenario).count()==0
    assert result['cash_fixed_and_reserved_rub']=='80000.00' and result['full_economic_cost_before_revenue_rates_rub']=='100000.00'
    assert [x['price_rub'] for x in result['scenarios'][:4]]==['88888.89','111111.12','116666.67','133333.34']
    assert result['scenarios'][0]['cash_break_even_met'] and not result['scenarios'][0]['full_break_even_met']
    assert result['scenarios'][1]['full_break_even_met'] and result['scenarios'][2]['minimum_profit_met'] and result['scenarios'][3]['target_profit_met']
    assert result['scenarios'][3]['within_user_reference_ceiling'] is False
    assert [x['economic_profit_rub'] for x in result['scenarios'][4:]]==['-28000.00','-10000.00','8000.00']
    assert result['scenarios'][-1]['economic_margin_percent']=='6.6666'
    assert all(result[k] is False for k in ('tax_model_verified','market_comparables_used','probability_of_winning_estimated','is_procurement_bid_recommendation','commercial_owner_go','external_submission_allowed'))
    for bad in ({'revenue_tax_percent':'96'},{'own_labor_rub':'-1'},{'external_direct_rub':'1.001'},{'accept_hypothetical_assumptions_only':False},{'minimum_profit_rub':'20001'},{'manual_bid_prices_rub':['100','100.00']},{'manual_bid_prices_rub':['0']},{'reference_ceiling_rub':'0'},{'assumption_note':'   '}):
        assert preview({**inputs,**bad}).status_code==422,bad
    for field in ('revenue_tax_percent','guarantee_financing_cost_rub','manual_bid_prices_rub'):
        assert preview({k:v for k,v in inputs.items() if k!=field}).status_code==422
    assert preview(inputs,token=b).status_code==404 and save(inputs,url=foreign).status_code==404
    r=save(inputs);assert r.status_code==201,r.text
    first=r.json();assert first['result']==result and first['revision']==1 and first['origin']=='EXPLICIT_USER_ASSUMPTIONS'
    assert save(inputs).json()==first
    changed={**inputs,'own_labor_rub':'30000'}
    assert save(changed).status_code==409 and save(inputs,rev=1).status_code==409
    assert save(changed,key='price-fixture-2').status_code==409
    assert save(changed,rev=1,key='price-fixture-2').status_code==201
    page=client.get(path,headers=headers,params={'limit':1}).json();assert page['has_more'] and page['items'][0]['revision']==2
    assert client.get(path,headers=headers,params={'offset':1}).json()['items']==[first]
    assert client.get(path,headers=_auth(b)).status_code==404
    assert client.get(same,headers=headers).json()['items']==[]
    invite=client.post('/api/saas/invitations',headers=headers,json={'role':'viewer','acquisition_channel':'referral'}).json()
    viewer=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':'viewer'}).json()['access_token'];_legal(client,viewer)
    assert client.get(path,headers=_auth(viewer)).status_code==403 and preview(inputs,token=viewer).status_code==403
    invite=client.post('/api/saas/invitations',headers=headers,json={'role':'analyst','acquisition_channel':'referral'}).json()
    analyst=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':'analyst'}).json()['access_token'];_legal(client,analyst)
    assert client.get(path,headers=_auth(analyst)).status_code==200 and preview(inputs,token=analyst).status_code==200
    assert save(inputs,rev=2,key='price-fixture-3',token=analyst).status_code==403
    assert save(inputs,rev=2,key='price-fixture-3',token=viewer).status_code==403
    assert session.query(CompanyPriceScenario).count()==2
    from sqlalchemy import update
    session.execute(update(CompanyPriceScenario).where(CompanyPriceScenario.id==first['scenario_id']).values(result_json={}))
    session.commit();assert client.get(path,headers=headers).status_code==409


def test_price_itemized_rollup_history_and_scope(client, session, monkeypatch):
    from copy import deepcopy

    from sqlalchemy import update

    from src.modules.saas_foundation.models import CompanyPriceScenario

    _, a=_seed(client,'Itemized A'); _, b=_seed(client,'Itemized B')
    _legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_company_price_scenarios_enabled':True});monkeypatch.setattr(saas,'get_settings',lambda:settings)
    headers=_auth(a);cases='/api/saas/company-portfolio/cases'
    def create(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']+'/price-scenarios'
    path=create(a,1);other=create(a,2);foreign=create(b,1)
    terms={'revenue_tax_percent':'6','variable_platform_fee_percent':'4','minimum_profit_rub':'5000','target_profit_rub':'20000','reference_ceiling_rub':'120000','manual_bid_prices_rub':['120000'],'assumption_note':' Synthetic itemized estimate only ','accept_hypothetical_assumptions_only':True}
    def line(category,title,unit,quantity,rate,source_kind='ASSUMPTION'):
        return {'category':category,'title':title,'unit':unit,'quantity':quantity,'rate_rub':rate,'source_kind':source_kind,'source_note':'Fixture basis, not independently verified'}
    estimate={'lines':[line('external_direct_rub','Paid services','h','40','1500','USER_REPORTED_QUOTE'),line('external_direct_rub','Fraction A','unit','0.3333','0.01'),line('external_direct_rub','Fraction B','unit','0.3333','0.01'),line('own_labor_rub','Own labor','h','10','2000','USER_REPORTED_ACTUAL'),line('cash_overhead_rub','Hosting','month','2','5000'),line('reserve_rub','Reserve','lot','1','5000')],'zero_cost_categories':['fixed_platform_fees_rub','guarantee_financing_cost_rub'],'terms':terms,'confirm_no_double_count':True}
    def preview(body=estimate,token=a,url=path):return client.post(url+'/itemized/preview',headers=_auth(token),json=body)
    def save(body=estimate,rev=0,key='estimate-fixture-1',token=a,url=path):return client.post(url+'/itemized',headers=_auth(token),json={'estimate':body,'expected_revision':rev,'idempotency_key':key})
    assert preview().status_code==404
    settings=settings.model_copy(update={'saas_company_price_itemized_enabled':True})
    r=preview();assert r.status_code==200,r.text
    out=r.json();detail=out['itemized_estimate'];aggregate=out['inputs']
    assert out['inputs_stored'] is False and session.query(CompanyPriceScenario).count()==0
    assert detail['schema']=='company_price_itemized_v1' and detail['rounding_policy']=='CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM'
    assert not detail['source_notes_independently_verified'] and not detail['double_count_independently_checked'] and not detail['external_submission_allowed']
    assert [row['amount_rub'] for row in detail['lines']]==['60000.00','0.01','0.01','20000.00','10000.00','5000.00']
    assert detail['lines'][0]['source_kind']=='USER_REPORTED_QUOTE' and detail['lines'][3]['source_kind']=='USER_REPORTED_ACTUAL'
    assert detail['category_totals_rub']=={k:aggregate[k] for k in ('external_direct_rub','own_labor_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub')}
    assert aggregate['external_direct_rub']=='60000.02' and aggregate['fixed_platform_fees_rub']=='0.00' and aggregate['assumption_note']=='Synthetic itemized estimate only'
    legacy=client.post(path+'/preview',headers=headers,json=aggregate);assert legacy.status_code==200 and legacy.json()['result']==out['result']
    invalid_cases=[]
    for field,value in [('quantity','0'),('quantity','0.00001'),('rate_rub','0'),('rate_rub','1.001'),('unit','   '),('source_note',''),('source_kind','VERIFIED_QUOTE'),('quantity',1.5)]:
        x=deepcopy(estimate);x['lines'][0][field]=value;invalid_cases.append(x)
    for zeros in ([],['external_direct_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'],['fixed_platform_fees_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub']):
        invalid_cases.append({**estimate,'zero_cost_categories':zeros})
    invalid_cases += [{**estimate,'confirm_no_double_count':False},{**estimate,'lines':[estimate['lines'][0]]*61},{**estimate,'lines':estimate['lines']+[estimate['lines'][0]]},{**estimate,'terms':{**terms,'external_direct_rub':'100'}},{**estimate,'terms':{**terms,'revenue_tax_percent':'96'}}]
    huge=deepcopy(estimate);huge['lines'][0].update(quantity='999999999',rate_rub='999999999999.99');invalid_cases.append(huge)
    for invalid in invalid_cases:
        assert preview(invalid).status_code==422,invalid
    assert preview(token=b).status_code==404 and save(url=foreign).status_code==404
    old=client.post(path,headers=headers,json={'scenario':aggregate,'expected_revision':0,'idempotency_key':'legacy-fixture'});assert old.status_code==201,old.text
    old_row=old.json();assert 'itemized_estimate' not in old_row
    assert save().status_code==409
    r=save(rev=1);assert r.status_code==201,r.text
    row=r.json();assert row['revision']==2 and row['inputs']==aggregate and row['result']==out['result'] and row['itemized_estimate']==detail
    assert save(rev=1).json()==row
    changed=deepcopy(estimate);changed['lines'][0]['source_note']='Different statement'
    assert save(changed,rev=1).status_code==409
    assert client.post(path,headers=headers,json={'scenario':aggregate,'expected_revision':1,'idempotency_key':'estimate-fixture-1'}).status_code==409
    assert client.get(path,headers=headers,params={'limit':30}).json()['items']==[row,old_row]
    assert client.get(other,headers=headers).json()['items']==[] and client.get(path,headers=_auth(b)).status_code==404
    for role in ('viewer','analyst'):
        invite=client.post('/api/saas/invitations',headers=headers,json={'role':role,'acquisition_channel':'referral'}).json()
        token=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':role}).json()['access_token'];_legal(client,token)
        assert preview(token=token).status_code==(403 if role=='viewer' else 200)
        assert save(rev=2,key='role-fixture',token=token).status_code==403
    settings=settings.model_copy(update={'saas_company_price_itemized_enabled':False})
    assert preview().status_code==404 and client.get(path,headers=headers,params={'limit':30}).json()['items']==[row,old_row]
    stored=session.get(CompanyPriceScenario,row['scenario_id']);damaged=deepcopy(stored.input_json);damaged['scenario']['external_direct_rub']='0.00'
    session.execute(update(CompanyPriceScenario).where(CompanyPriceScenario.id==row['scenario_id']).values(input_json=damaged));session.commit()
    assert client.get(path,headers=headers).status_code==409


def test_cost_evidence_exact_version_line_bytes_and_scope(client, session, monkeypatch):
    import hashlib

    from sqlalchemy import update

    from src.modules.saas_foundation import company_cost_evidence as evidence
    from src.modules.saas_foundation.models import CompanyCostEvidence

    _, a=_seed(client,'Cost documents A'); _, b=_seed(client,'Cost documents B')
    _legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_company_price_scenarios_enabled':True,'saas_company_price_itemized_enabled':True});monkeypatch.setattr(saas,'get_settings',lambda:settings)
    headers=_auth(a);cases='/api/saas/company-portfolio/cases'
    def create(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']+'/price-scenarios'
    path=create(a,1);other=create(a,2);foreign=create(b,1)
    estimate={'lines':[{'category':'own_labor_rub','title':'Develop','unit':'h','quantity':'2.5','rate_rub':'2000','source_kind':'USER_REPORTED_QUOTE','source_note':'User copy fixture'}], 'zero_cost_categories':['external_direct_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'],'terms':{'revenue_tax_percent':'6','variable_platform_fee_percent':'0','minimum_profit_rub':'0','target_profit_rub':'1000','manual_bid_prices_rub':[],'assumption_note':'Synthetic test only','accept_hypothetical_assumptions_only':True},'confirm_no_double_count':True}
    def save_estimate(rev, key):
        r=client.post(path+'/itemized',headers=headers,json={'estimate':estimate,'expected_revision':rev,'idempotency_key':key});assert r.status_code==201,r.text
        return r.json()
    first=save_estimate(0,'evidence-first');second=save_estimate(1,'evidence-second')
    legacy=client.post(path,headers=headers,json={'scenario':first['inputs'],'expected_revision':2,'idempotency_key':'evidence-legacy'});assert legacy.status_code==201,legacy.text
    legacy=legacy.json()
    def url(row,base=path,ordinal=1):return base+'/'+row['scenario_id']+f'/lines/{ordinal}/evidence'
    u=url(first);v=url(second);assert client.get(u,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_cost_evidence_enabled':True})
    binding=client.get(u,headers=headers).json();digest=binding['line_sha256'];assert len(digest)==64 and binding['evidence'] is None and binding['line_amount_rub']=='5000.00'
    assert client.get(v,headers=headers).json()['line_sha256']!=digest
    assert client.get(u+'/download',headers=headers).status_code==404
    raw=b'%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF';sha=hashlib.sha256(raw).hexdigest()
    params={'line_sha256':digest,'document_kind':'QUOTE','format_hint':'pdf','confirm_user_supplied':True}
    def upload(target=u,body=raw,token=a,**overrides):return client.post(target,headers=_auth(token),params={**params,**overrides},content=body)
    assert upload(confirm_user_supplied=False).status_code==422
    assert upload(line_sha256='0'*64).status_code==409 and upload(target=v).status_code==409
    assert upload(body=b'not a document').status_code==422
    assert upload(body=b'x'*(2*1024*1024+1)).status_code==413
    assert upload(document_kind='VERIFIED_QUOTE').status_code==422
    assert upload(token=b).status_code==404 and upload(target=url(first,other)).status_code==404 and upload(target=url(first,foreign),token=b).status_code==404
    assert client.get(url(first,ordinal=2),headers=headers).status_code==404
    assert client.get(url(legacy),headers=headers).status_code==409
    assert upload(target=url(legacy)).status_code==409
    r=upload();assert r.status_code==201,r.text
    saved=r.json();assert saved['inspection']['sha256']==sha and saved['scenario_id']==first['scenario_id'] and saved['scenario_revision']==1 and saved['line_sha256']==digest and saved['line_ordinal']==1
    assert saved['stored_bytes_reverified'] and all(saved[k] is False for k in ('document_origin_verified','cost_amount_verified','payment_verified','external_submission_allowed'))
    assert 'text_preview' not in saved['inspection']
    assert upload().json()==saved and upload(document_kind='INVOICE').status_code==409 and upload(body=raw.replace(b'1 0 obj',b'2 0 obj')).status_code==409
    assert client.get(u,headers=headers).json()['evidence']==saved and client.get(v,headers=headers).json()['evidence'] is None
    dl=client.get(u+'/download',headers=headers);assert dl.status_code==200 and dl.content==raw and dl.headers['x-artifact-sha256']==sha and dl.headers['cache-control']=='private, no-store' and 'attachment;' in dl.headers['content-disposition']
    assert client.get(u+'/download',headers=_auth(b)).status_code==404
    for role in ('viewer','analyst'):
        invite=client.post('/api/saas/invitations',headers=headers,json={'role':role,'acquisition_channel':'referral'}).json()
        token=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':role}).json()['access_token'];_legal(client,token)
        assert client.get(u,headers=_auth(token)).status_code==(403 if role=='viewer' else 200)
        assert client.get(u+'/download',headers=_auth(token)).status_code==(403 if role=='viewer' else 200)
        assert upload(token=token).status_code==403
    monkeypatch.setattr(evidence,'MAX_DOCUMENTS_PER_TENANT',1)
    assert upload(target=v,line_sha256=client.get(v,headers=headers).json()['line_sha256']).status_code==429
    assert upload().json()==saved and session.query(CompanyCostEvidence).count()==1
    # Adding the file does not revise the underlying financial scenario or promote its provenance.
    assert client.get(path,headers=headers,params={'limit':30}).json()['items']==[legacy,second,first]
    session.execute(update(CompanyCostEvidence).where(CompanyCostEvidence.id==saved['evidence_id']).values(line_sha256='0'*64));session.commit()
    assert client.get(u,headers=headers).status_code==409 and client.get(u+'/download',headers=headers).status_code==409
    session.execute(update(CompanyCostEvidence).where(CompanyCostEvidence.id==saved['evidence_id']).values(line_sha256=digest,raw_bytes=raw.replace(b'1 0 obj',b'9 0 obj')));session.commit()
    assert client.get(u,headers=headers).status_code==409 and client.get(u+'/download',headers=headers).status_code==409


def test_actual_cost_snapshots_partial_complete_and_scope(client,session,monkeypatch):
    from copy import deepcopy

    from sqlalchemy import update

    from src.modules.saas_foundation.models import CompanyActualCostSnapshot

    _,a=_seed(client,'Actual A');_,b=_seed(client,'Actual B');_legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_company_price_scenarios_enabled':True,'saas_company_price_itemized_enabled':True});monkeypatch.setattr(saas,'get_settings',lambda:settings)
    headers=_auth(a);cases='/api/saas/company-portfolio/cases'
    def create(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']+'/price-scenarios'
    path=create(a,1);other=create(a,2);foreign=create(b,1)
    def cost(cat,title,qty,rate,kind='ASSUMPTION'):
        return {'category':cat,'title':title,'unit':'h' if cat=='own_labor_rub' else 'unit','quantity':qty,'rate_rub':rate,'source_kind':kind,'source_note':'Synthetic test source'}
    estimate={'lines':[cost('own_labor_rub','Development','10','1000'),cost('external_direct_rub','License','2','500'),cost('reserve_rub','Reserve','1','100')],'zero_cost_categories':['cash_overhead_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'],'terms':{'revenue_tax_percent':'6','variable_platform_fee_percent':'0','minimum_profit_rub':'0','target_profit_rub':'1000','manual_bid_prices_rub':[],'assumption_note':'Synthetic plan','accept_hypothetical_assumptions_only':True},'confirm_no_double_count':True}
    def plan(rev,key):
        r=client.post(path+'/itemized',headers=headers,json={'estimate':estimate,'expected_revision':rev,'idempotency_key':key});assert r.status_code==201,r.text
        return r.json()
    first=plan(0,'actual-plan-1');second=plan(1,'actual-plan-2');legacy=client.post(path,headers=headers,json={'scenario':first['inputs'],'expected_revision':2,'idempotency_key':'actual-legacy'}).json()
    def url(row,base=path):return base+'/'+row['scenario_id']+'/actual-costs'
    u=url(first);v=url(second);assert client.get(u,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_actual_costs_enabled':True})
    pre=client.get(u,headers=headers).json();digest=pre['baseline_sha256'];assert pre['items']==[] and len(digest)==64 and len(pre['planned_lines'])==3
    assert client.get(v,headers=headers).json()['baseline_sha256']!=digest
    partial={'baseline_sha256':digest,'as_of':'2026-11-15','observations':[{'ordinal':1,'quantity':'12','rate_rub':'1000','source_note':'Reported cumulative hours'}],'unplanned_costs':[cost('cash_overhead_rub','Extra hosting','0.3333','0.01','USER_REPORTED_ACTUAL')],'note':'Cumulative to date, synthetic','confirm_cumulative_user_report':True,'confirm_no_double_count':True}
    def preview(body=partial,token=a,target=u):return client.post(target+'/preview',headers=_auth(token),json=body)
    def save(body=partial,rev=0,key='actual-snapshot-1',token=a,target=u):return client.post(target,headers=_auth(token),json={'snapshot':body,'expected_revision':rev,'idempotency_key':key})
    r=preview();assert r.status_code==200,r.text
    result=r.json()['result'];assert not r.json()['inputs_stored'] and session.query(CompanyActualCostSnapshot).count()==0
    assert result['lines'][0]['actual_amount_rub']=='12000.00' and result['lines'][0]['variance_rub']=='2000.00' and result['lines'][0]['variance_percent']=='20.0000'
    assert result['lines'][1]['status']=='NOT_REPORTED' and result['lines'][1]['actual_amount_rub'] is None and result['lines'][1]['variance_rub'] is None
    assert result['totals']['planned_rub']=='11100.00' and result['totals']['reported_total_rub']=='12000.01' and result['totals']['matched_planned_rub']=='10000.00'
    assert result['totals']['missing_planned_lines']==2 and result['totals']['reported_vs_full_plan_rub'] is None
    assert result['unplanned_costs'][0]['actual_amount_rub']=='0.01'
    assert all(result[k] is False for k in ('payment_verified','actual_amounts_independently_verified','contract_cost_coverage_complete','contract_execution_verified','revenue_or_profit_verified','external_submission_allowed'))
    assert preview(target=v).status_code==409 and preview(token=b).status_code==404 and save(target=url(first,other)).status_code==404 and save(target=url(first,foreign),token=b).status_code==404
    assert client.get(url(legacy),headers=headers).status_code==409
    for changes in ({'as_of':'2099-01-01'},{'confirm_cumulative_user_report':False},{'confirm_no_double_count':False},{'observations':partial['observations']*2},{'observations':[{**partial['observations'][0],'ordinal':4}]},{'observations':[{**partial['observations'][0],'quantity':'0'}]},{'observations':[{**partial['observations'][0],'quantity':'1.00001'}]},{'observations':[{**partial['observations'][0],'source_note':' '} ]},{'observations':[],'unplanned_costs':[]},{'unplanned_costs':[cost('cash_overhead_rub','Extra','1','100')]},{'unplanned_costs':[cost('cash_overhead_rub','Extra','999999999','999999999999.99','USER_REPORTED_ACTUAL')]}):
        assert preview({**partial,**changes}).status_code==422,changes
    r=save();assert r.status_code==201,r.text
    row=r.json();assert row['revision']==1 and row['result']==result and save().json()==row
    complete=deepcopy(partial);complete['observations']+= [{'ordinal':2,'quantity':'2','rate_rub':'500','source_note':'Reported license cost'},{'ordinal':3,'quantity':'0','rate_rub':'0','source_note':'Reported no reserve used'}]
    assert save(complete).status_code==409 and save(complete,key='actual-snapshot-2').status_code==409
    assert save({**complete,'as_of':'2026-11-14'},rev=1,key='actual-snapshot-2').status_code==409
    r=save(complete,rev=1,key='actual-snapshot-2');assert r.status_code==201,r.text
    row2=r.json();t=row2['result']['totals'];assert t['reported_total_rub']=='13000.01' and t['reported_vs_full_plan_rub']=='1900.01' and t['all_planned_lines_reported'] and not row2['result']['contract_cost_coverage_complete']
    assert row2['result']['lines'][2]['actual_amount_rub']=='0.00' and row2['result']['lines'][2]['variance_percent']=='-100.0000'
    page=client.get(u,headers=headers,params={'limit':1}).json();assert page['items']==[row2] and page['has_more'];assert client.get(u,headers=headers,params={'offset':1}).json()['items']==[row]
    assert client.get(v,headers=headers).json()['items']==[]
    for role in ('viewer','analyst'):
        invite=client.post('/api/saas/invitations',headers=headers,json={'role':role,'acquisition_channel':'referral'}).json();token=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':role}).json()['access_token'];_legal(client,token)
        assert preview(token=token).status_code==(403 if role=='viewer' else 200)
        assert save(complete,rev=2,key='actual-role-test',token=token).status_code==403
    assert client.get(path,headers=headers,params={'limit':30}).json()['items']==[legacy,second,first]
    session.execute(update(CompanyActualCostSnapshot).where(CompanyActualCostSnapshot.id==row['snapshot_id']).values(result_json={}));session.commit()
    assert client.get(u,headers=headers).status_code==409


def test_actual_evidence_separate_rows_revisions_and_integrity(client,session,monkeypatch):
    import hashlib

    from sqlalchemy import update

    from src.modules.saas_foundation import company_actual_evidence as evidence
    from src.modules.saas_foundation.models import CompanyActualCostEvidence

    _,a=_seed(client,'Actual evidence A');_,b=_seed(client,'Actual evidence B');_legal(client,a);_legal(client,b)
    settings=saas.get_settings().model_copy(update={'saas_company_price_scenarios_enabled':True,'saas_company_price_itemized_enabled':True,'saas_company_actual_costs_enabled':True});monkeypatch.setattr(saas,'get_settings',lambda:settings)
    headers=_auth(a);cases='/api/saas/company-portfolio/cases'
    def create(token,n):
        r=client.post(cases,headers=_auth(token),json={'registry_number':f'{n:019d}'});assert r.status_code==201,r.text
        return cases+'/'+r.json()['case_id']+'/price-scenarios'
    path=create(a,1);other=create(a,2);foreign=create(b,1)
    def cost(category,title,kind):
        return {'category':category,'title':title,'unit':'h','quantity':'2.5','rate_rub':'2000','source_kind':kind,'source_note':'Synthetic source'}
    estimate={'lines':[cost('own_labor_rub','Development','ASSUMPTION'),cost('external_direct_rub','License','USER_REPORTED_QUOTE')],'zero_cost_categories':['cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'],'terms':{'revenue_tax_percent':'6','variable_platform_fee_percent':'0','minimum_profit_rub':'0','target_profit_rub':'1000','manual_bid_prices_rub':[],'assumption_note':'Synthetic plan','accept_hypothetical_assumptions_only':True},'confirm_no_double_count':True}
    def plan(revision,key):
        r=client.post(path+'/itemized',headers=headers,json={'estimate':estimate,'expected_revision':revision,'idempotency_key':key});assert r.status_code==201,r.text;return r.json()
    first=plan(0,'act-ev-plan-1');second=plan(1,'act-ev-plan-2');base=path+'/'+first['scenario_id']+'/actual-costs';different=path+'/'+second['scenario_id']+'/actual-costs'
    digest=client.get(base,headers=headers).json()['baseline_sha256']
    snapshot={'baseline_sha256':digest,'as_of':'2026-11-15','observations':[{'ordinal':1,'quantity':'3','rate_rub':'2000','source_note':'Reported timesheet'}],'unplanned_costs':[cost('cash_overhead_rub','Extra','USER_REPORTED_ACTUAL')],'note':'Synthetic report','confirm_cumulative_user_report':True,'confirm_no_double_count':True}
    def report(rev,key,payload=snapshot):
        r=client.post(base,headers=headers,json={'snapshot':payload,'expected_revision':rev,'idempotency_key':key});assert r.status_code==201,r.text;return r.json()
    r1=report(0,'act-ev-report-1');r2=report(1,'act-ev-report-2',{**snapshot,'observations':[{'ordinal':1,'quantity':'0','rate_rub':'0','source_note':'Correction, no expense'}]})
    def url(row=r1,kind='PLANNED',ordinal=1,root=base):return root+'/'+row['snapshot_id']+f'/rows/{kind}/{ordinal}/evidence'
    u=url();v=url(r2);extra=url(kind='UNPLANNED');assert client.get(u,headers=headers).status_code==404
    settings=settings.model_copy(update={'saas_company_actual_evidence_enabled':True})
    binding=client.get(u,headers=headers).json();line_digest=binding['line_sha256'];assert len(line_digest)==64 and binding['actual_amount_rub']=='6000.00' and binding['evidence'] is None
    assert client.get(v,headers=headers).json()['actual_amount_rub']=='0.00'
    extra_digest=client.get(extra,headers=headers).json()['line_sha256'];assert extra_digest!=line_digest and client.get(v,headers=headers).json()['line_sha256']!=line_digest
    assert client.get(url(ordinal=2),headers=headers).status_code==409
    assert client.get(url(ordinal=3),headers=headers).status_code==404
    assert client.get(url(kind='INVALID'),headers=headers).status_code==422
    assert client.get(url(root=different),headers=headers).status_code==404
    raw=b'%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF';sha=hashlib.sha256(raw).hexdigest()
    params={'line_sha256':line_digest,'format_hint':'pdf','document_kind':'TIMESHEET','confirm_user_supplied':True}
    def upload(target=u,body=raw,token=a,**overrides):return client.post(target,headers=_auth(token),params={**params,**overrides},content=body)
    assert upload(confirm_user_supplied=False).status_code==422 and upload(target=v).status_code==409 and upload(target=extra).status_code==409
    assert upload(body=b'not pdf').status_code==422 and upload(body=b'x'*(2*1024*1024+1)).status_code==413
    assert upload(document_kind='QUOTE').status_code==422 and upload(target=url(ordinal=2)).status_code==409
    assert upload(token=b).status_code==404 and upload(target=url(root=different)).status_code==404
    assert upload(target=url(root=other+'/'+first['scenario_id']+'/actual-costs')).status_code==404
    assert upload(target=url(root=foreign+'/'+first['scenario_id']+'/actual-costs'),token=b).status_code==404
    assert client.get(u+'/download',headers=headers).status_code==404
    res=upload();assert res.status_code==201,res.text
    saved=res.json();assert saved['inspection']['sha256']==sha and saved['snapshot_id']==r1['snapshot_id'] and saved['row_kind']=='PLANNED'
    assert saved['stored_bytes_reverified'] and saved['origin']=='USER_SUPPLIED_UNATTESTED' and all(saved[k] is False for k in ('actual_amount_verified','payment_verified','document_origin_verified','contract_execution_verified','external_submission_allowed'))
    assert 'text_preview' not in saved['inspection'] and upload().json()==saved
    assert upload(document_kind='INVOICE').status_code==409 and upload(body=raw.replace(b'1 0 obj',b'2 0 obj')).status_code==409
    dl=client.get(u+'/download',headers=headers);assert dl.status_code==200 and dl.content==raw and dl.headers['x-artifact-sha256']==sha and dl.headers['cache-control']=='private, no-store'
    assert client.get(u+'/download',headers=_auth(b)).status_code==404
    res=upload(target=extra,line_sha256=extra_digest,document_kind='PAYMENT_RECORD');assert res.status_code==201,res.text
    assert res.json()['row_kind']=='UNPLANNED' and res.json()['payment_verified'] is False
    assert client.get(v,headers=headers).json()['evidence'] is None
    for role in ('viewer','analyst'):
        invite=client.post('/api/saas/invitations',headers=headers,json={'role':role,'acquisition_channel':'referral'}).json();token=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':role}).json()['access_token'];_legal(client,token)
        assert client.get(u,headers=_auth(token)).status_code==(403 if role=='viewer' else 200)
        assert client.get(u+'/download',headers=_auth(token)).status_code==(403 if role=='viewer' else 200)
        assert upload(token=token).status_code==403
    monkeypatch.setattr(evidence,'MAX_DOCUMENTS_PER_TENANT',2)
    assert upload(target=v,line_sha256=client.get(v,headers=headers).json()['line_sha256']).status_code==429
    assert upload().json()==saved and session.query(CompanyActualCostEvidence).count()==2
    assert client.get(base,headers=headers).json()['items']==[r2,r1]
    session.execute(update(CompanyActualCostEvidence).where(CompanyActualCostEvidence.id==saved['evidence_id']).values(line_sha256='0'*64));session.commit()
    assert client.get(u,headers=headers).status_code==409 and client.get(u+'/download',headers=headers).status_code==409
    session.execute(update(CompanyActualCostEvidence).where(CompanyActualCostEvidence.id==saved['evidence_id']).values(line_sha256=line_digest,raw_bytes=raw.replace(b'1 0 obj',b'9 0 obj')));session.commit()
    assert client.get(u,headers=headers).status_code==409 and client.get(u+'/download',headers=headers).status_code==409
