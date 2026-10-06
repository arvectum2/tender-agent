from datetime import UTC, datetime, timedelta

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
