from datetime import UTC, datetime, timedelta

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord
from src.shared.enums import DealStatus


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


def test_mobile_inbox_lists_pending_and_accepts_go(client, session):
    deal = _deal("DL-MOB-001", "3001")
    session.add(deal)
    session.commit()

    inbox = client.get("/mobile/v1/inbox")
    assert inbox.status_code == 200
    assert inbox.json()["summary"]["needs_attention"] == 1
    assert inbox.json()["items"][0]["human_decision"] == "PENDING"

    response = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "GO",
            "rationale": "Manager approved from iPhone",
            "reason_codes": ["FIT"],
            "idempotency_key": "mobile-go-3001",
            "actor_ref": "ios-test",
        },
    )
    assert response.status_code == 200
    assert response.json()["human_decision"] == "GO"
    assert response.json()["needs_attention"] is False

    repeated = client.post(
        f"/mobile/v1/procurements/{deal.deal_id}/decision",
        json={
            "action": "GO",
            "rationale": "Manager approved from iPhone",
            "reason_codes": ["FIT"],
            "idempotency_key": "mobile-go-3001",
            "actor_ref": "ios-test",
        },
    )
    assert repeated.status_code == 200
    count = session.query(DecisionRecord).filter(DecisionRecord.deal_id == deal.deal_id).count()
    assert count == 1


def test_mobile_defer_hides_future_item_until_due(client, session):
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


def test_mobile_defer_requires_date(client, session):
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
