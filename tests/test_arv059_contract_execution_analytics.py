from src.modules.dashboard_snapshots.models import DashboardMetricRecord
from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import EventRecord
from src.modules.kpi_learning.models import KPILearningSet
from src.modules.postmortems.models import PostmortemSet
from src.tender_research.models import ProcurementTender
from tests.test_recovery_r5_integration import _prepare_r5_final_context


def _build_closure_analytics_context(client, session):
    package = _prepare_r5_final_context(client, session)
    deal_id = package["intake"]["deal_id"]

    report = client.post("/deal-closure-reports/build", json={"deal_id": deal_id})
    assert report.status_code == 201
    package["closure_report"] = report.json()

    postmortem = client.post("/postmortems/build", json={"deal_id": deal_id})
    assert postmortem.status_code == 201
    package["postmortem"] = postmortem.json()
    return package


def _metric_map(payload: dict) -> dict[str, float | str | None]:
    metrics = payload["records"][0]["metrics"]
    return {
        item["metric_code"]: (
            item["metric_value_numeric"]
            if item["metric_value_numeric"] is not None
            else item["metric_value_text"]
        )
        for item in metrics
    }


def test_arv059_projects_full_source_bound_lifecycle_without_learning_mutation(
    client, session
):
    package = _build_closure_analytics_context(client, session)
    deal_id = package["intake"]["deal_id"]

    before_events = session.query(EventRecord).filter_by(deal_id=deal_id).count()
    before_kpi = session.query(KPILearningSet).filter_by(deal_id=deal_id).count()
    before_postmortems = session.query(PostmortemSet).filter_by(deal_id=deal_id).count()

    response = client.get(f"/contract-execution-analytics/deals/{deal_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["deal_id"] == deal_id
    assert payload["supplier_contract"]["state"] == "OBSERVED"
    assert payload["supplier_contract"]["evidence"]
    assert payload["execution"]["state"] == "OBSERVED"
    assert payload["execution"]["evidence"]
    assert payload["execution_stages"]
    assert all(
        stage["state"] == "OBSERVED" and stage["evidence"]
        for stage in payload["execution_stages"]
    )
    assert payload["payment"]["state"] == "OBSERVED"
    assert payload["payment"]["expected_amount"] == 150000.0
    assert payload["payment"]["collected_amount"] == 150000.0
    assert payload["payment"]["overdue_days"] == 5
    assert payload["payment"]["evidence"]
    assert payload["timing"]["state"] == "OBSERVED"
    assert payload["timing"]["overdue_payment_days"] == 5
    assert payload["penalties"]["state"] == "OBSERVED"
    assert payload["penalties"]["signals"]
    assert payload["penalties"]["monetary_penalty_state"] == "UNKNOWN"
    assert payload["penalties"]["monetary_penalty_amount"] is None
    assert payload["outcome"]["state"] == "OBSERVED"
    assert payload["outcome"]["evidence"]
    assert payload["closure"]["state"] == "OBSERVED"
    assert payload["closure_health"]["state"] == "OBSERVED"
    assert payload["postmortem"]["state"] == "OBSERVED"
    assert payload["postmortem"]["evidence"]
    assert payload["actual_price"]["state"] == "UNKNOWN"
    assert payload["actual_price"]["value_numeric"] is None
    assert payload["learning_promotion_performed"] is False

    assert (
        session.query(EventRecord).filter_by(deal_id=deal_id).count() == before_events
    )
    assert (
        session.query(KPILearningSet).filter_by(deal_id=deal_id).count() == before_kpi
    )
    assert (
        session.query(PostmortemSet).filter_by(deal_id=deal_id).count()
        == before_postmortems
    )


def test_arv059_partial_deal_keeps_missing_lifecycle_facts_unknown(client, session):
    deal = Deal(
        deal_id="DEAL-ARV059-PARTIAL",
        title="Partial ARV-059 deal",
        customer_name="АО Частичный заказчик",
        procurement_number=None,
        procurement_channel=None,
        initial_source_type="MANUAL",
        direction_type="TENDER",
        domain_type="GOODS",
        current_status="NEW",
    )
    session.add(deal)
    session.commit()

    response = client.get(f"/contract-execution-analytics/deals/{deal.deal_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["procurement"]["state"] == "UNKNOWN"
    assert payload["supplier_contract"]["state"] == "UNKNOWN"
    assert payload["execution"]["state"] == "UNKNOWN"
    assert payload["execution_stages"] == []
    assert payload["payment"]["state"] == "UNKNOWN"
    assert payload["timing"]["state"] == "UNKNOWN"
    assert payload["penalties"]["state"] == "UNKNOWN"
    assert payload["actual_price"]["state"] == "UNKNOWN"
    assert payload["outcome"]["state"] == "UNKNOWN"
    assert payload["closure"]["state"] == "UNKNOWN"
    assert payload["closure_health"]["state"] == "UNKNOWN"
    assert payload["postmortem"]["state"] == "UNKNOWN"
    assert payload["learning_promotion_performed"] is False


def test_arv059_procurement_link_is_exact_number_not_name_fallback(client, session):
    deal = Deal(
        deal_id="DEAL-ARV059-PROC",
        title="Поставка кабеля",
        customer_name="АО Заказчик",
        procurement_number="0590000000000000001",
        procurement_channel="EIS",
        initial_source_type="EIS",
        direction_type="TENDER",
        domain_type="GOODS",
        current_status="NEW",
    )
    exact = ProcurementTender(
        source="eis",
        external_id="arv059-exact",
        registry_number=deal.procurement_number,
        title="Точный источник закупки",
        status="COMPLETED",
        nmck_amount=990000.0,
        currency="RUB",
        eis_url="https://zakupki.gov.ru/epz/order/notice/059-exact",
    )
    same_name_wrong_number = ProcurementTender(
        source="eis",
        external_id="arv059-wrong",
        registry_number="0599999999999999999",
        title=deal.title,
        status="COMPLETED",
        nmck_amount=111000.0,
        currency="RUB",
        eis_url="https://zakupki.gov.ru/epz/order/notice/059-wrong",
    )
    session.add_all([deal, exact, same_name_wrong_number])
    session.commit()

    payload = client.get(f"/contract-execution-analytics/deals/{deal.deal_id}").json()

    assert payload["procurement"]["state"] == "OBSERVED"
    refs = {item["source_ref"] for item in payload["procurement"]["evidence"]}
    assert f"eis:{deal.procurement_number}" in refs
    assert "eis:0599999999999999999" not in refs


def test_arv059_dashboard_consumes_same_lifecycle_projection(client, session):
    package = _build_closure_analytics_context(client, session)
    deal_id = package["intake"]["deal_id"]

    projection = client.get(f"/contract-execution-analytics/deals/{deal_id}")
    assert projection.status_code == 200
    projected = projection.json()

    dashboard = client.post(
        "/dashboards/build",
        json={"scope_type": "DEAL", "scope_ref": deal_id},
    )
    assert dashboard.status_code == 201
    metrics = _metric_map(dashboard.json())

    assert (
        metrics["lifecycle_contract_status"]
        == projected["supplier_contract"]["value_text"]
    )
    assert metrics["lifecycle_execution_status"] == projected["execution"]["value_text"]
    assert metrics["lifecycle_execution_phase"] == projected["timing"]["current_phase"]
    assert metrics["lifecycle_payment_status"] == projected["payment"]["status"]
    assert (
        metrics["lifecycle_collected_amount"]
        == projected["payment"]["collected_amount"]
    )
    assert metrics["lifecycle_overdue_days"] == projected["payment"]["overdue_days"]
    assert metrics["lifecycle_claim_status"] == projected["penalties"]["claim_status"]
    assert metrics["lifecycle_outcome_code"] == projected["outcome"]["value_text"]
    assert metrics["lifecycle_closure_code"] == projected["closure"]["value_text"]
    assert (
        metrics["lifecycle_closure_health"] == projected["closure_health"]["value_text"]
    )
    assert metrics["lifecycle_actual_price_state"] == "UNKNOWN"
    assert metrics["lifecycle_learning_promotion"] == "disabled"

    persisted_codes = {
        item.metric_code
        for item in session.query(DashboardMetricRecord)
        .filter_by(
            dashboard_snapshot_id=dashboard.json()["records"][0][
                "dashboard_snapshot_id"
            ]
        )
        .all()
    }
    assert "lifecycle_outcome_code" in persisted_codes
    assert "lifecycle_actual_price_state" in persisted_codes
