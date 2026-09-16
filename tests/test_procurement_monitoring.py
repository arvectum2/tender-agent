from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.modules.procurement_monitoring.schemas import DocumentState, SourceSnapshot
from src.modules.procurement_monitoring.service import build_alert_event, diff_snapshots, snapshot_fingerprint


def snapshot(**overrides):
    values = {
        "source": "eis",
        "external_id": "0123456789",
        "source_url": "https://example.test/notice/0123456789",
        "application_deadline": datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        "nmck_amount": Decimal("100000.00"),
        "status": "published",
        "notice_revision": "1",
        "cancelled": False,
        "documents": [DocumentState(source_document_id="doc-1", sha256="aaa", revision="1")],
    }
    values.update(overrides)
    return SourceSnapshot(**values)


def test_unchanged_replay_is_idempotent():
    before = snapshot()
    after = snapshot()
    diff = diff_snapshots(before, after)
    assert diff.outcome == "UNCHANGED"
    assert build_alert_event(after, diff) is None
    assert snapshot_fingerprint(before) == snapshot_fingerprint(after)


def test_deadline_change_is_source_bound_and_deterministic():
    before = snapshot()
    after = snapshot(application_deadline=before.application_deadline + timedelta(days=1))
    diff = diff_snapshots(before, after)
    assert diff.outcome == "CHANGED"
    assert [change.field for change in diff.changes] == ["application_deadline"]
    assert build_alert_event(after, diff).event_key == build_alert_event(after, diff).event_key


def test_document_revision_change_is_detected():
    before = snapshot()
    after = snapshot(
        notice_revision="2",
        documents=[DocumentState(source_document_id="doc-1", sha256="bbb", revision="2")],
    )
    diff = diff_snapshots(before, after)
    assert diff.outcome == "CHANGED"
    assert {change.field for change in diff.changes} == {"notice_revision", "document_set"}


def test_status_and_cancellation_change_are_detected():
    diff = diff_snapshots(snapshot(), snapshot(status="cancelled", cancelled=True))
    assert diff.outcome == "CHANGED"
    assert {change.field for change in diff.changes} == {"status", "cancelled"}


def test_ambiguous_source_state_fails_closed():
    diff = diff_snapshots(snapshot(), snapshot(ambiguity_reason="active_revision_ambiguous"))
    assert diff.outcome == "NEEDS_REVIEW"
    assert diff.reason == "active_revision_ambiguous"


def test_identity_change_fails_closed():
    diff = diff_snapshots(snapshot(), snapshot(external_id="other"))
    assert diff.outcome == "NEEDS_REVIEW"
    assert diff.reason == "watch_target_identity_changed"


def test_persisted_watch_replay_does_not_duplicate_feed_or_audit(session):
    from sqlalchemy import func, select
    from src.modules.event_log.models import EventRecord
    from src.modules.procurement_monitoring.models import ProcurementWatchEvent
    from src.modules.procurement_monitoring.schemas import WatchTarget
    from src.modules.procurement_monitoring.service import check_watch, create_watch
    from src.tender_research.models import ProcurementTender

    tender = ProcurementTender(source="eis", external_id="watch-1", title="Watched tender", status="published")
    session.add(tender)
    session.commit()
    watch = create_watch(session, WatchTarget(source="eis", external_id="watch-1"))
    assert check_watch(session, watch.id) is None
    tender.application_deadline = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    session.commit()
    first = check_watch(session, watch.id)
    assert first is not None and first.outcome == "CHANGED"
    assert check_watch(session, watch.id) is None
    assert session.scalar(select(func.count()).select_from(ProcurementWatchEvent)) == 1
    assert session.scalar(select(func.count()).select_from(EventRecord).where(EventRecord.source_module_id == "procurement_monitoring")) == 1
