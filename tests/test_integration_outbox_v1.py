from src.modules.integration_outbox.schemas import AdapterStatus
from src.modules.integration_outbox.service import enqueue_event, list_outbox


def test_replay_is_idempotent(session):
    a = enqueue_event(session, event_type="analysis_completed", tenant_id="c1", aggregate_type="analysis_run", aggregate_id="r1", source_key="r1", data={"status":"completed"})
    b = enqueue_event(session, event_type="analysis_completed", tenant_id="c1", aggregate_type="analysis_run", aggregate_id="r1", source_key="r1", data={"status":"completed"})
    session.commit()
    assert a.id == b.id
    assert len(list_outbox(session, tenant_id="c1")) == 1

def test_tenant_filter_isolation(session):
    enqueue_event(session, event_type="analysis_completed", tenant_id="c1", aggregate_type="analysis_run", aggregate_id="r1", source_key="1")
    enqueue_event(session, event_type="analysis_completed", tenant_id="c2", aggregate_type="analysis_run", aggregate_id="r2", source_key="2")
    session.commit()
    assert {row.tenant_id for row in list_outbox(session, tenant_id="c1")} == {"c1"}

def test_secret_like_fields_are_removed_recursively(session):
    row = enqueue_event(session, event_type="review_required", aggregate_type="deal", aggregate_id="d1", source_key="x", data={"reason":"check", "token":"bad", "nested":{"password":"bad", "ok":"yes"}})
    session.commit()
    assert row.envelope["data"] == {"reason":"check", "nested":{"ok":"yes"}}

def test_adapter_is_fail_closed():
    status = AdapterStatus()
    assert status.enabled is False and status.mode == "disabled"

def test_monitoring_change_emits_one_outbox_event(session):
    from datetime import UTC, datetime

    from src.modules.procurement_monitoring.schemas import WatchTarget
    from src.modules.procurement_monitoring.service import check_watch, create_watch
    from src.tender_research.models import ProcurementTender
    tender = ProcurementTender(source="eis", external_id="outbox-watch", title="Watched", status="published")
    session.add(tender); session.commit()
    watch = create_watch(session, WatchTarget(source="eis", external_id="outbox-watch"))
    assert check_watch(session, watch.id) is None
    tender.application_deadline = datetime(2026, 9, 21, 12, 0, tzinfo=UTC); session.commit()
    assert check_watch(session, watch.id) is not None
    assert check_watch(session, watch.id) is None
    rows = list_outbox(session, event_type="monitoring_alert")
    assert len(rows) == 1 and rows[0].aggregate_id == watch.id
