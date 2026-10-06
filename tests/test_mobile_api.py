from datetime import UTC, datetime, timedelta

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.main import app
from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord
from src.modules.mobile_api.auth import (
    get_mobile_auth_secret,
    issue_mobile_token,
    pairing_code,
    require_mobile_bearer,
    resolve_mobile_auth_secret,
    verify_mobile_token,
)
from src.modules.mobile_api.models import (
    MobileDeviceAccess,
    MobileDeviceRegistration,
    MobilePushDelivery,
)
from src.modules.mobile_api.push import (
    APNsSendResult,
    build_mobile_push_payload,
    dispatch_due_deferred_notifications,
    dispatch_mobile_push_event,
    send_apns_notification,
)
from src.shared.config.settings import Settings
from src.shared.enums import DealStatus

TEST_SECRET = "test-mobile-secret-0123456789-abcdefghijklmnopqrstuvwxyz"


def _deal(deal_id: str, number: str) -> Deal:
    return Deal(
        deal_id=deal_id,
        title=f"Tender {number}",
        customer_name="Customer",
        procurement_number=number,
        procurement_channel="PORTAL",
        initial_source_type="portal_ingest",
        direction_type="SERVICE",
        domain_type="IT",
        current_status=DealStatus.NEW,
    )


def _allow_mobile(device_id: str = "device-test-001") -> None:
    app.dependency_overrides[require_mobile_bearer] = lambda: device_id




def test_mobile_routes_use_dedicated_auth_boundary():
    assert "/mobile" not in Settings().pilot_auth_protected_prefixes.split(",")


def test_mobile_auth_secret_prefers_explicit_secret():
    explicit = "x" * 40
    settings = Settings(
        _env_file=None,
        mobile_auth_secret=explicit,
        pilot_auth_username="operator",
        pilot_auth_password="pilot-secret-" + ("y" * 32),
    )

    assert resolve_mobile_auth_secret(settings) == explicit


def test_mobile_auth_secret_derives_from_safe_pilot_password():
    password = "pilot-secret-" + ("z" * 32)
    settings = Settings(
        _env_file=None,
        mobile_auth_secret=None,
        pilot_auth_username="operator",
        pilot_auth_password=password,
    )

    derived = resolve_mobile_auth_secret(settings)
    assert derived is not None
    assert len(derived) == 64
    assert derived != password




def test_pairing_code_issues_and_verifies_bearer(client):
    app.dependency_overrides[get_mobile_auth_secret] = lambda: TEST_SECRET
    code = pairing_code(TEST_SECRET)

    response = client.post(
        "/mobile/v1/pair",
        json={
            "pairing_code": code,
            "device_id": "device-pair-001",
            "device_name": "Test iPhone",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["device_id"] == "device-pair-001"
    assert verify_mobile_token(TEST_SECRET, body["access_token"]) == "device-pair-001"


def test_mobile_bearer_rejects_missing_token(client):
    app.dependency_overrides[get_mobile_auth_secret] = lambda: TEST_SECRET

    response = client.get("/mobile/v1/inbox")

    assert response.status_code == 401


def test_revoked_mobile_device_bearer_is_rejected(client, session):
    app.dependency_overrides[get_mobile_auth_secret] = lambda: TEST_SECRET
    code = pairing_code(TEST_SECRET)
    paired = client.post(
        "/mobile/v1/pair",
        json={
            "pairing_code": code,
            "device_id": "device-revoke-auth-001",
            "device_name": "Lost iPhone",
        },
    )
    assert paired.status_code == 200
    token = paired.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/mobile/v1/inbox", headers=headers).status_code == 200
    revoked = client.delete(
        "/mobile/v1/devices/device-revoke-auth-001",
        headers=headers,
    )
    assert revoked.status_code == 204

    access = session.query(MobileDeviceAccess).one()
    assert access.device_id == "device-revoke-auth-001"
    assert access.is_revoked is True
    assert access.revoked_at is not None

    rejected = client.get("/mobile/v1/inbox", headers=headers)
    assert rejected.status_code == 401
    assert rejected.json()["detail"] == "Mobile device access was revoked."


def test_mobile_token_expires():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    token, _ = issue_mobile_token(
        TEST_SECRET,
        device_id="device-expiry-001",
        ttl_days=1,
        now=now,
    )

    assert verify_mobile_token(TEST_SECRET, token, now=now + timedelta(hours=23)) == "device-expiry-001"
    assert verify_mobile_token(TEST_SECRET, token, now=now + timedelta(days=1)) is None


def test_mobile_inbox_lists_pending_and_accepts_go(client, session):
    _allow_mobile("device-go-001")
    deal = _deal("DL-MOB-001", "3001")
    session.add(deal)
    session.commit()

    inbox = client.get("/mobile/v1/inbox")
    assert inbox.status_code == 200
    assert inbox.json()["summary"]["needs_attention"] == 1
    assert inbox.json()["items"][0]["human_decision"] == "PENDING"

    payload = {
        "action": "GO",
        "rationale": "Manager approved from iPhone",
        "reason_codes": ["FIT"],
        "idempotency_key": "mobile-go-3001",
    }
    response = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["human_decision"] == "GO"
    assert response.json()["needs_attention"] is False

    repeated = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json=payload,
    )
    assert repeated.status_code == 200
    decisions = (
        session.query(DecisionRecord)
        .filter(DecisionRecord.deal_id == deal.deal_id)
        .all()
    )
    assert len(decisions) == 1
    assert decisions[0].decided_by_ref == "ios:device-go-001"

    canonical = client.get("/procurement-portfolio").json()
    canonical_item = next(item for item in canonical["items"] if item["deal_id"] == deal.deal_id)
    assert canonical_item["decision"] == "GO"
    assert canonical_item["decision_source"] == "HUMAN"


def test_mobile_defer_hides_future_item_until_due(client, session):
    _allow_mobile()
    deal = _deal("DL-MOB-002", "3002")
    session.add(deal)
    session.commit()

    deferred_until = datetime.now(UTC) + timedelta(days=1)
    response = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "DEFER",
            "deferred_until": deferred_until.isoformat(),
            "idempotency_key": "mobile-defer-3002",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["human_decision"] == "DEFER"
    assert body["needs_attention"] is False

    inbox = client.get("/mobile/v1/inbox").json()
    assert inbox["summary"]["deferred"] == 1
    assert inbox["summary"]["needs_attention"] == 0

    canonical = client.get("/procurement-portfolio").json()
    canonical_item = next(item for item in canonical["items"] if item["deal_id"] == deal.deal_id)
    assert canonical_item["decision"] == "NEEDS_REVIEW"
    assert canonical_item["decision_source"] == "HUMAN"


def test_mobile_no_go_is_visible_in_canonical_portfolio(client, session):
    _allow_mobile("device-no-go-001")
    deal = _deal("DL-MOB-004", "3004")
    session.add(deal)
    session.commit()

    response = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "NO_GO",
            "rationale": "Manager rejected from iPhone",
            "reason_codes": ["ECONOMICS"],
            "idempotency_key": "mobile-no-go-3004",
        },
    )
    assert response.status_code == 200
    assert response.json()["human_decision"] == "NO_GO"
    assert response.json()["needs_attention"] is False

    canonical = client.get("/procurement-portfolio").json()
    canonical_item = next(item for item in canonical["items"] if item["deal_id"] == deal.deal_id)
    assert canonical_item["decision"] == "NO_GO"
    assert canonical_item["decision_source"] == "HUMAN"
    assert canonical_item["decision_rationale"] == "Manager rejected from iPhone"
    assert canonical_item["decision_reason_codes"] == ["ECONOMICS"]


def test_mobile_defer_requires_date(client, session):
    _allow_mobile()
    deal = _deal("DL-MOB-003", "3003")
    session.add(deal)
    session.commit()

    response = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "DEFER",
            "idempotency_key": "mobile-defer-missing",
        },
    )
    assert response.status_code == 422

def test_mobile_device_registration_is_idempotent_and_never_echoes_token(client, session):
    _allow_mobile("device-push-001")
    first_token = "ab" * 32
    response = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": first_token,
            "environment": "sandbox",
            "device_name": "Test iPhone",
            "app_version": "0.7.0",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "device-push-001"
    assert body["environment"] == "sandbox"
    assert body["enabled"] is True
    assert "apns_token" not in body

    second_token = "cd" * 32
    repeated = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": second_token,
            "environment": "production",
            "device_name": "Test iPhone renamed",
            "app_version": "0.7.1",
        },
    )
    assert repeated.status_code == 200
    rows = session.query(MobileDeviceRegistration).all()
    assert len(rows) == 1
    assert rows[0].device_id == "device-push-001"
    assert rows[0].apns_token == second_token
    assert rows[0].apns_environment == "production"
    assert rows[0].device_name == "Test iPhone renamed"


def test_mobile_device_registration_rejects_invalid_apns_token(client):
    _allow_mobile("device-push-invalid")
    response = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": "zz" * 32,
            "environment": "sandbox",
        },
    )
    assert response.status_code == 422


def test_mobile_device_can_revoke_only_itself(client, session):
    _allow_mobile("device-push-revoke")
    register = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": "ef" * 32,
            "environment": "sandbox",
        },
    )
    assert register.status_code == 200

    forbidden = client.delete("/mobile/v1/devices/another-device")
    assert forbidden.status_code == 403

    revoked = client.delete("/mobile/v1/devices/device-push-revoke")
    assert revoked.status_code == 204
    row = session.query(MobileDeviceRegistration).one()
    assert row.is_enabled is False
    assert row.apns_token == ""


def test_mobile_push_payload_deep_links_to_procurement_and_digest():
    procurement = build_mobile_push_payload(
        event_type="REPORT_READY",
        title="Отчёт готов",
        body="Проверьте закупку",
        deal_id="DL-MOB-PUSH-001",
    )
    assert procurement["event_type"] == "REPORT_READY"
    assert procurement["deal_id"] == "DL-MOB-PUSH-001"
    assert procurement["deep_link"] == "tenderagent://procurement/DL-MOB-PUSH-001"

    digest = build_mobile_push_payload(
        event_type="DEADLINE_RISK",
        title="Срок",
        body="Есть закупки с близким сроком",
    )
    assert digest["deep_link"] == "tenderagent://digest"
    assert "deal_id" not in digest


def test_apns_sender_uses_http2_token_auth_and_expected_topic(tmp_path):
    private_key = ec.generate_private_key(ec.SECP256R1())
    key_path = tmp_path / "AuthKey_TEST.p8"
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["topic"] = request.headers["apns-topic"]
        captured["push_type"] = request.headers["apns-push-type"]
        return httpx.Response(
            200,
            headers={"apns-id": "apns-mock-001"},
            request=request,
        )

    settings = Settings(
        _env_file=None,
        mobile_apns_enabled=True,
        mobile_apns_team_id="TEAM123456",
        mobile_apns_key_id="KEY1234567",
        mobile_apns_private_key_path=str(key_path),
        mobile_apns_bundle_id="com.arvectum.tenderagent",
    )
    result = send_apns_notification(
        token="ab" * 32,
        environment="sandbox",
        payload=build_mobile_push_payload(
            event_type="REPORT_READY",
            title="Отчёт готов",
            body="Проверьте закупку",
            deal_id="DL-MOB-APNS-001",
        ),
        settings=settings,
        transport=httpx.MockTransport(handler),
    )

    assert result.ok is True
    assert result.apns_id == "apns-mock-001"
    assert captured["url"].startswith(
        "https://api.sandbox.push.apple.com/3/device/"
    )
    assert captured["authorization"].startswith("bearer ")
    assert captured["topic"] == "com.arvectum.tenderagent"
    assert captured["push_type"] == "alert"


def test_mobile_push_delivery_is_idempotent_per_device_and_source(client, session):
    _allow_mobile("device-push-send")
    register = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": "12" * 32,
            "environment": "sandbox",
        },
    )
    assert register.status_code == 200

    calls = []

    def fake_sender(registration, payload):
        calls.append((registration.device_id, payload["deep_link"]))
        return APNsSendResult(ok=True, status_code=200, apns_id="apns-test-1")

    first = dispatch_mobile_push_event(
        session,
        event_type="REPORT_READY",
        source_key="report-ready-source-1",
        title="Новый отчёт",
        body="Tender 3005",
        deal_id="DL-MOB-005",
        sender=fake_sender,
    )
    second = dispatch_mobile_push_event(
        session,
        event_type="REPORT_READY",
        source_key="report-ready-source-1",
        title="Новый отчёт",
        body="Tender 3005",
        deal_id="DL-MOB-005",
        sender=fake_sender,
    )

    assert first.sent == 1
    assert second.duplicate == 1
    assert calls == [
        ("device-push-send", "tenderagent://procurement/DL-MOB-005")
    ]
    deliveries = session.query(MobilePushDelivery).all()
    assert len(deliveries) == 1
    assert deliveries[0].status == "SENT"
    assert deliveries[0].attempts == 1


def test_due_deferred_decision_dispatches_deep_linked_push(client, session):
    _allow_mobile("device-push-due")
    deal = _deal("DL-MOB-006", "3006")
    session.add(deal)
    session.commit()
    register = client.post(
        "/mobile/v1/devices",
        json={
            "apns_token": "34" * 32,
            "environment": "sandbox",
        },
    )
    assert register.status_code == 200

    deferred_until = datetime.now(UTC) - timedelta(minutes=1)
    decision = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "DEFER",
            "deferred_until": deferred_until.isoformat(),
            "idempotency_key": "mobile-due-3006",
        },
    )
    assert decision.status_code == 200

    payloads = []

    def fake_sender(registration, payload):
        payloads.append(payload)
        return APNsSendResult(ok=True, status_code=200, apns_id="apns-due-1")

    summaries = dispatch_due_deferred_notifications(
        session,
        now=datetime.now(UTC),
        sender=fake_sender,
    )
    assert len(summaries) == 1
    assert summaries[0].sent == 1
    assert payloads[0]["event_type"] == "DEFERRED_DUE"
    assert payloads[0]["deal_id"] == deal.deal_id
    assert payloads[0]["deep_link"] == f"tenderagent://procurement/{deal.deal_id}"
