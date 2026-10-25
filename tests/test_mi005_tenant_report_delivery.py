"""MI005: tenant auth, immutable report bundles, disabled-by-default API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.market_intelligence import report_router
from src.modules.market_intelligence.report_delivery import (
    ReportAccessError,
    ReportBundleStore,
)
from src.modules.saas_foundation import router as saas
from src.shared.config.settings import Settings

_SOURCE = Path(__file__).resolve().parents[1] / (
    "data/market_intelligence/power_quality/mi003_evaluation.v1.json"
)


def _evaluation():
    return json.loads(_SOURCE.read_text(encoding="utf-8"))


def test_published_bundle_immutable_with_sha_and_tenant_scope(tmp_path):
    store = ReportBundleStore(tmp_path / "bundles")
    receipt = store.publish("ten_alice", _evaluation(), report_id="rep_01")
    assert receipt["market_size_rub"] is None
    assert receipt["state"] == "source_limited_qualification_not_market_census"
    assert set(receipt["assets"]) == {"html", "csv", "json"}
    assert store.list_reports("ten_bob") == []
    assert len(store.list_reports("ten_alice")) == 1
    for fmt in ("html", "csv", "json"):
        content, mime = store.read("ten_alice", "rep_01", fmt)
        assert content
        assert len(receipt["assets"][fmt]["sha256"]) == 64
        assert len(content) == receipt["assets"][fmt]["bytes"]
        assert "utf-8" in mime
    with pytest.raises(ReportAccessError, match="report not found"):
        store.read("ten_bob", "rep_01", "json")
    with pytest.raises(ReportAccessError, match="immutable"):
        store.publish("ten_alice", _evaluation(), report_id="rep_01")


def test_tenant_id_and_report_path_traversal_forbidden(tmp_path):
    store = ReportBundleStore(tmp_path / "bundles")
    for candidate in ("../a", "ten/../../other", ".hidden", "a", "ten?"):
        with pytest.raises(ReportAccessError):
            store.publish(candidate, _evaluation())
    store.publish("ten_alice", _evaluation(), report_id="rep_01")
    for report_id in ("../../etc/passwd", "../rep_01", "a", ".dot"):
        with pytest.raises(ReportAccessError):
            store.read("ten_alice", report_id, "json")
    with pytest.raises(ReportAccessError):
        store.read("ten_alice", "rep_01", "../../../secrets")


def test_corrupted_or_symlinked_bundle_denied(tmp_path):
    store = ReportBundleStore(tmp_path / "bundles")
    store.publish("ten_alice", _evaluation(), report_id="rep_01")
    file = tmp_path / "bundles/ten_alice/rep_01/report.html"
    file.write_text("tampered", encoding="utf-8")
    with pytest.raises(ReportAccessError, match="available|checksum"):
        store.read("ten_alice", "rep_01", "html")
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    file.unlink()
    file.symlink_to(target)
    with pytest.raises(ReportAccessError):
        store.read("ten_alice", "rep_01", "html")


def test_cannot_publish_fake_tam_or_claimed_winning_epc(tmp_path):
    store = ReportBundleStore(tmp_path / "bundles")
    evaluation = _evaluation()
    evaluation["verified_hardware_market_size_rub"] = "99999999"
    with pytest.raises(ReportAccessError, match="cannot publish"):
        store.publish("ten_alice", evaluation)
    evaluation["verified_hardware_market_size_rub"] = None
    evaluation["known_winning_epc"] = ["unverified"]
    with pytest.raises(ReportAccessError, match="cannot publish"):
        store.publish("ten_alice", evaluation)


def _settings(tmp_path, *, report_gate=True, saas_gate=True):
    return Settings(
        _env_file=None,
        saas_foundation_enabled=saas_gate,
        market_intelligence_report_delivery_enabled=report_gate,
        pilot_auth_enabled=True,
        pilot_auth_username="operator",
        pilot_auth_password="unit-test-only-operator-password-of-safe-length-2026",
        arvectum_data_dir=str(tmp_path),
    )


@pytest.fixture
def config(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    monkeypatch.setattr(report_router, "get_settings", lambda: settings)
    monkeypatch.setattr(saas, "get_settings", lambda: settings)
    return settings


def _operator_headers():
    import base64

    raw = b"operator:unit-test-only-operator-password-of-safe-length-2026"
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def _seed_tenant(client, name):
    customer = client.post("/customers", json={
        "legal_name": name,
        "customer_status": "PROSPECT",
    })
    assert customer.status_code == 201, customer.text
    r = client.post("/api/operator/saas/tenants", json={
        "customer_id": customer.json()["customer_id"]
    }, headers=_operator_headers())
    assert r.status_code == 201, r.text
    tenant = r.json()
    reply = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": tenant["invitation"]["invitation_code"],
        "display_name": name + " pilot owner",
    })
    assert reply.status_code == 201, reply.text
    return tenant["tenant_id"], reply.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _accept_legal(client, token):
    legal = client.get("/api/saas/legal", headers=_headers(token))
    assert legal.status_code == 200
    details = legal.json()
    confirm = client.post("/api/saas/legal/accept", headers=_headers(token), json={
        "terms_version": details["terms_version"],
        "privacy_version": details["privacy_version"],
        "confirm_read": True,
    })
    assert confirm.status_code == 200, confirm.text


def test_http_report_download_requires_valid_tenant_and_legal_gate(client, config, tmp_path):
    ten_a, token_a = _seed_tenant(client, "ООО Тест-Поставщик А")
    _ten_b, token_b = _seed_tenant(client, "ООО Тест-Поставщик Б")
    store = ReportBundleStore(tmp_path / "market_intelligence_reports")
    store.publish(ten_a, _evaluation(), report_id="rep_tenant_a")

    path = "/api/saas/market-intelligence/reports"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=_headers("saas_wrong")).status_code == 401
    assert client.get(path, headers=_headers(token_a)).status_code == 428
    _accept_legal(client, token_a)
    _accept_legal(client, token_b)

    own_list = client.get(path, headers=_headers(token_a))
    assert own_list.status_code == 200, own_list.text
    assert [r["report_id"] for r in own_list.json()["reports"]] == ["rep_tenant_a"]
    other_list = client.get(path, headers=_headers(token_b))
    assert other_list.status_code == 200
    assert other_list.json()["reports"] == []

    target = path + "/rep_tenant_a/html"
    own = client.get(target, headers=_headers(token_a))
    assert own.status_code == 200
    assert own.headers["content-disposition"].startswith("attachment;")
    assert own.headers["cache-control"] == "private, no-store"
    assert own.headers["x-content-type-options"] == "nosniff"
    assert b"POWER QUALITY" in own.content
    cross_tenant = client.get(target, headers=_headers(token_b))
    assert cross_tenant.status_code == 404
    assert b"POWER QUALITY" not in cross_tenant.content
    assert client.get(path + "/rep_tenant_a/json", headers=_headers(token_a)).json()[
        "schema_version"
    ] == "mi003-power-quality-evaluation/0.1"


def test_viewer_can_only_read_existing_tenant_report(client, config, tmp_path):
    tenant, owner = _seed_tenant(client, "ООО Тест-Доступ Для Наблюдателя")
    store = ReportBundleStore(tmp_path / "market_intelligence_reports")
    store.publish(tenant, _evaluation(), report_id="rep_viewer")
    _accept_legal(client, owner)
    invite = client.post("/api/saas/invitations", headers=_headers(owner),
                         json={"role": "viewer", "acquisition_channel": "pilot"})
    assert invite.status_code == 200, invite.text
    redeemed = client.post("/api/saas/invitations/redeem", json={
        "invitation_code": invite.json()["invitation_code"],
        "display_name": "Наблюдатель Power Quality",
    })
    assert redeemed.status_code == 201
    viewer = redeemed.json()["access_token"]
    _accept_legal(client, viewer)
    read = client.get("/api/saas/market-intelligence/reports/rep_viewer/csv",
                      headers=_headers(viewer))
    assert read.status_code == 200
    assert b"priority_hypothesis" in read.content
    forbidden = client.post("/api/saas/invitations",
                            headers=_headers(viewer),
                            json={"role": "admin"})
    assert forbidden.status_code == 403


def test_report_endpoint_disabled_by_second_feature_gate(client, config, tmp_path, monkeypatch):
    _tenant, token = _seed_tenant(client, "ООО Тест Выключенного Доступа")
    _accept_legal(client, token)
    monkeypatch.setattr(
        report_router, "get_settings",
        lambda: _settings(tmp_path, report_gate=False),
    )
    reply = client.get("/api/saas/market-intelligence/reports",
                       headers=_headers(token))
    assert reply.status_code == 404


def test_missing_report_avoids_exposing_physical_paths(client, config):
    _tenant, token = _seed_tenant(client, "ООО Тест Неизвестного Отчёта")
    _accept_legal(client, token)
    reply = client.get("/api/saas/market-intelligence/reports/rep_missing/json",
                       headers=_headers(token))
    assert reply.status_code == 404
    assert "Users/master" not in reply.text
    assert "market_intelligence_reports" not in reply.text


def test_legal_gate_is_not_overridden_by_report_storage(monkeypatch):
    def deny(*args):
        raise HTTPException(428, "privacy agreement needed")
    monkeypatch.setattr(report_router, "legal_required", deny)
    with pytest.raises(HTTPException) as exc:
        report_router.legal_required(None, None)
    assert exc.value.status_code == 428
