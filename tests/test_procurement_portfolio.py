from datetime import UTC, datetime

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord, EventRecord
from src.modules.outcome_intake.models import OutcomeIntakeRecord, OutcomeIntakeSet
from src.modules.procurement_portfolio.service import build_procurement_portfolio
from src.modules.tender_screening.models import TenderScreeningRecord
from src.shared.enums import DealStatus


def _deal(deal_id: str, number: str, status: str = DealStatus.NEW) -> Deal:
    return Deal(
        deal_id=deal_id,
        title=f"Tender {number}",
        customer_name="Customer",
        procurement_number=number,
        procurement_channel="PORTAL",
        initial_source_type="portal_ingest",
        direction_type="SUPPLY",
        domain_type="IT",
        current_status=status,
    )


def test_portfolio_aggregates_decision_submission_and_outcome(session):
    go = _deal("DL-900001", "1001")
    no_go = _deal("DL-900002", "1002")
    session.add_all([go, no_go])
    session.flush()

    session.add(
        DecisionRecord(
            decision_id="DEC-900001",
            deal_id=go.deal_id,
            decision_code="PORTFOLIO_BID_DECISION",
            decided_by_type="HUMAN",
            rationale="Strong fit",
            payload_json={"decision": "GO", "reason_codes": ["FIT"]},
        )
    )
    session.add(
        EventRecord(
            event_id="EVT-900001",
            deal_id=go.deal_id,
            event_code="submission_execution_submitted",
            source_module_id="M-033",
            severity="INFO",
            payload_json={},
        )
    )
    outcome_set = OutcomeIntakeSet(
        outcome_intake_set_id="OUT-SET-900001",
        deal_id=go.deal_id,
        post_submission_tracker_set_id="PST-900001",
        outcome_status="RECORDED",
    )
    session.add(outcome_set)
    session.flush()
    session.add(
        OutcomeIntakeRecord(
            outcome_intake_id="OUT-900001",
            outcome_intake_set_id=outcome_set.outcome_intake_set_id,
            outcome_code="WON",
            effective_at=datetime.now(UTC),
            rationale="Best price",
        )
    )

    session.add(
        TenderScreeningRecord(
            screening_id="SCR-900002",
            deal_id=no_go.deal_id,
            intake_id="INT-900002",
            document_set_id="DOC-SET-900002",
            tender_summary_id="SUM-900002",
            result_status="FAIL",
            screening_score=0.2,
            rationale_text="Outside target",
            factor_breakdown_json={},
            reason_codes_json=["NON_TARGET_DOMAIN"],
            recommended_next_status="REJECTED_EARLY",
        )
    )
    session.commit()

    result = build_procurement_portfolio(session)
    assert result["summary"]["total_considered"] == 2
    assert result["summary"]["go"] == 1
    assert result["summary"]["no_go"] == 1
    assert result["summary"]["submitted"] == 1
    assert result["summary"]["won"] == 1
    assert result["summary"]["win_rate"] == 1.0
    assert result["summary"]["no_go_reason_counts"] == {"NON_TARGET_DOMAIN": 1}


def test_portfolio_api_records_manual_decision(client, session):
    deal = _deal("DL-900003", "1003")
    session.add(deal)
    session.commit()

    response = client.post(
        f"/procurement-portfolio/{deal.deal_id}/decision",
        json={
            "decision": "NO_GO",
            "rationale": "On-site visit is mandatory",
            "reason_codes": ["ONSITE_REQUIRED"],
            "decided_by_ref": "operator",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "NO_GO"
    assert body["decision_source"] == "HUMAN"
    assert body["decision_reason_codes"] == ["ONSITE_REQUIRED"]

    summary = client.get("/procurement-portfolio").json()["summary"]
    assert summary["no_go"] == 1
    assert summary["no_go_reason_counts"]["ONSITE_REQUIRED"] == 1


def test_portfolio_ui_is_available(client):
    response = client.get("/procurement-portfolio/ui")
    assert response.status_code == 200
    assert "Портфель закупок" in response.text


def test_portfolio_api_creates_manual_procurement(client):
    response = client.post(
        "/procurement-portfolio",
        json={
            "procurement_number": "2001",
            "title": "Website development",
            "customer_name": "Youth Center",
            "source_url": "https://zakupki.gov.ru/example",
            "direction_type": "SERVICE",
            "domain_type": "IT",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["procurement_number"] == "2001"
    assert body["decision"] == "UNDECIDED"

    duplicate = client.post(
        "/procurement-portfolio",
        json={
            "procurement_number": "2001",
            "title": "Website development",
            "customer_name": "Youth Center",
            "source_url": "https://zakupki.gov.ru/example",
            "direction_type": "SERVICE",
            "domain_type": "IT",
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deal_id"] == body["deal_id"]
