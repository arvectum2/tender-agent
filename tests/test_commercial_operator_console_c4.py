from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord, EventRecord
from src.modules.status_engine.models import DealStatusHistory
from src.modules.status_engine.service import seed_default_rules
from src.shared.db.base import utcnow
from src.shared.enums import ChangedByType, DealStatus


def _prepare_demo_deal(client) -> str:
    payload = client.post(
        "/commercial-prebid-demo/run",
        json={"fixture_name": "commercial_mvp_demo", "provider": "stub"},
    ).json()
    return payload["deal_id"]


def test_commercial_operator_console_views_render_for_demo_deal(client):
    deal_id = _prepare_demo_deal(client)

    dashboard = client.get("/commercial-console")
    kanban = client.get("/commercial-console/kanban")
    tender_card = client.get(f"/commercial-console/deals/{deal_id}")
    report = client.get(f"/commercial-console/deals/{deal_id}/report")
    requirements = client.get(f"/commercial-console/deals/{deal_id}/requirements")
    risks = client.get(f"/commercial-console/deals/{deal_id}/risks")
    traces = client.get(f"/commercial-console/deals/{deal_id}/runtime-traces")
    decision = client.get(f"/commercial-console/deals/{deal_id}/decision")

    assert dashboard.status_code == 200
    assert "Commercial Operator Dashboard" in dashboard.text
    assert kanban.status_code == 200
    assert "Procurement Kanban" in kanban.text
    assert deal_id in kanban.text
    assert tender_card.status_code == 200 and deal_id in tender_card.text
    assert report.status_code == 200 and "Pre-Bid Report View" in report.text
    assert requirements.status_code == 200 and "Requirements" in requirements.text
    assert risks.status_code == 200 and "Risks" in risks.text
    assert traces.status_code == 200 and "Runtime Trace Review" in traces.text
    assert decision.status_code == 200 and "Decision Action View" in decision.text


def test_commercial_operator_console_action_records_event_and_decision(client, session):
    deal_id = _prepare_demo_deal(client)

    response = client.post(
        f"/commercial-console/deals/{deal_id}/actions",
        json={
            "action": "collect_tkp",
            "operator_ref": "commercial.operator",
            "rationale": "Need supplier commercial inputs before bid drafting.",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    decision = session.query(DecisionRecord).filter_by(decision_id=payload["decision_id"]).one()
    event = session.query(EventRecord).filter_by(event_id=payload["recorded_event_id"]).one()

    assert decision.decision_code == "OPERATOR_MARKED_COLLECT_TKP"
    assert event.event_code == "commercial_operator_action_recorded"
    assert event.payload_json["action"] == "collect_tkp"


def test_commercial_operator_kanban_filters_and_excludes_archived_deals(client, session):
    deal_id = _prepare_demo_deal(client)
    deal = session.query(Deal).filter_by(deal_id=deal_id).one()
    deal.customer_name = "Kanban Customer"
    deal.procurement_number = "KBN-2026-001"
    deal.priority_bucket = "P1"
    session.commit()

    filtered = client.get(
        "/commercial-console/kanban",
        params={
            "status": DealStatus.NEW.value,
            "priority_bucket": "P1",
            "customer_name": "Kanban",
            "procurement_number": "KBN-2026-001",
            "q": "Customer",
        },
    )
    assert filtered.status_code == 200
    assert deal_id in filtered.text
    assert "data-status='NEW'" in filtered.text
    assert "data-status='CANDIDATE'" not in filtered.text

    deal.archived_at = utcnow()
    session.commit()
    archived = client.get("/commercial-console/kanban")
    assert archived.status_code == 200
    assert deal_id not in archived.text


def test_commercial_operator_kanban_status_change_uses_canonical_engine(client, session):
    seed_default_rules(session)
    deal_id = _prepare_demo_deal(client)

    accepted = client.post(
        f"/commercial-console/kanban/deals/{deal_id}/status",
        json={
            "to_status": DealStatus.CANDIDATE.value,
            "operator_ref": "commercial.operator",
            "reason": "Human triage moved the procurement to candidate review.",
        },
    )
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["from_status"] == DealStatus.NEW.value
    assert payload["to_status"] == DealStatus.CANDIDATE.value
    assert payload["changed_by_type"] == ChangedByType.HUMAN.value
    assert payload["changed_by_ref"] == "commercial.operator"

    session.expire_all()
    deal = session.query(Deal).filter_by(deal_id=deal_id).one()
    assert deal.current_status == DealStatus.CANDIDATE
    history = session.query(DealStatusHistory).filter_by(deal_id=deal_id).all()
    assert [entry.to_status for entry in history] == [DealStatus.NEW, DealStatus.CANDIDATE]

    blocked = client.post(
        f"/commercial-console/kanban/deals/{deal_id}/status",
        json={
            "to_status": DealStatus.SUBMISSION.value,
            "operator_ref": "commercial.operator",
            "reason": "This invalid jump must remain blocked.",
        },
    )
    assert blocked.status_code == 422

    session.expire_all()
    deal = session.query(Deal).filter_by(deal_id=deal_id).one()
    assert deal.current_status == DealStatus.CANDIDATE
    blocked_events = (
        session.query(EventRecord)
        .filter_by(deal_id=deal_id, event_code="deal_status_transition_blocked")
        .all()
    )
    assert len(blocked_events) == 1
