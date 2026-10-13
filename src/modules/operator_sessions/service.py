from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.event_log.service import append_event_record
from src.modules.integration_tasks.models import (
    IntegrationTaskRecord,
    IntegrationTaskSet,
)
from src.modules.operator_sessions.models import (
    OperatorSessionItem,
    OperatorSessionRecord,
    OperatorSessionSet,
)
from src.modules.operator_sessions.schemas import (
    AcknowledgeOperatorSessionItemRequest,
    BuildOperatorSessionRequest,
)
from src.shared.control_package import (
    ensure_scope_exists,
    latest_action_queue_context,
    latest_integration_task_set,
    latest_workspace_feed_context,
    resolve_scope_deal_id,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    EventSeverity,
    OperatorSessionItemStatus,
    OperatorSessionItemType,
    OperatorSessionStatus,
    WorkspaceItemType,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_operator_session_id, next_operator_session_set_id
from src.shared.validation import require_non_empty


def _get_set(session: Session, operator_session_set_id: str) -> OperatorSessionSet:
    record = session.scalar(
        select(OperatorSessionSet).where(OperatorSessionSet.operator_session_set_id == operator_session_set_id)
    )
    if not record:
        raise NotFoundError(f"Operator session set '{operator_session_set_id}' was not found")
    return record


def _get_record(session: Session, operator_session_id: str) -> OperatorSessionRecord:
    record = session.scalar(
        select(OperatorSessionRecord).where(OperatorSessionRecord.operator_session_id == operator_session_id)
    )
    if not record:
        raise NotFoundError(f"Operator session record '{operator_session_id}' was not found")
    return record


def _get_records(session: Session, operator_session_set_id: str) -> list[OperatorSessionRecord]:
    return list(
        session.scalars(
            select(OperatorSessionRecord)
            .where(OperatorSessionRecord.operator_session_set_id == operator_session_set_id)
            .order_by(OperatorSessionRecord.created_at.asc(), OperatorSessionRecord.id.asc())
        )
    )


def _get_items(session: Session, operator_session_id: str) -> list[OperatorSessionItem]:
    return list(
        session.scalars(
            select(OperatorSessionItem)
            .where(OperatorSessionItem.operator_session_id == operator_session_id)
            .order_by(OperatorSessionItem.created_at.asc(), OperatorSessionItem.id.asc())
        )
    )


def _latest_integration_task_set(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[IntegrationTaskSet | None, list[IntegrationTaskRecord]]:
    # Historical private name kept for call sites and monkeypatchable tests.
    return latest_integration_task_set(session, scope_type, scope_ref)

def build_operator_session(session: Session, payload: BuildOperatorSessionRequest) -> OperatorSessionSet:
    ensure_scope_exists(session, payload.scope_type, payload.scope_ref)
    session_set = OperatorSessionSet(
        operator_session_set_id=next_operator_session_set_id(session, OperatorSessionSet.operator_session_set_id),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        session_status=OperatorSessionStatus.OPEN,
    )
    session.add(session_set)
    session.flush()
    deal_id = resolve_scope_deal_id(session, payload.scope_type, payload.scope_ref)
    try:
        workspace_set, _workspace_record, workspace_items = latest_workspace_feed_context(
            session, payload.scope_type, payload.scope_ref
        )
        queue_set, queue_records = latest_action_queue_context(session, payload.scope_type, payload.scope_ref)
        integration_task_set, integration_tasks = _latest_integration_task_set(
            session, payload.scope_type, payload.scope_ref
        )
        if not workspace_set:
            raise ValidationError("Operator session requires persisted workspace feed context")
        if not queue_set or not queue_records:
            raise ValidationError("Operator session requires persisted action queue context")
        if not integration_task_set:
            raise ValidationError("Operator session requires persisted integration task context")

        record = OperatorSessionRecord(
            operator_session_id=next_operator_session_id(session, OperatorSessionRecord.operator_session_id),
            operator_session_set_id=session_set.operator_session_set_id,
            opened_by_ref=require_non_empty(payload.opened_by_ref, "opened_by_ref"),
            summary_text=(
                f"Operator session for {payload.scope_type}:{payload.scope_ref}: "
                f"workspace_items={len(workspace_items)}, queue_items={len(queue_records)}, integration_tasks={len(integration_tasks)}."
            ),
        )
        session.add(record)
        session.flush()

        item_specs: list[dict] = []
        for queue_record, _approvals in queue_records:
            item_specs.append(
                {
                    "item_code": queue_record.action_code,
                    "item_type": OperatorSessionItemType.QUEUE_ITEM,
                    "source_ref": queue_record.action_queue_id,
                    "item_status": OperatorSessionItemStatus.VISIBLE,
                }
            )
        for task in integration_tasks:
            item_specs.append(
                {
                    "item_code": task.integration_task_id,
                    "item_type": OperatorSessionItemType.TASK,
                    "source_ref": task.integration_task_id,
                    "item_status": OperatorSessionItemStatus.VISIBLE,
                }
            )
        for item in workspace_items:
            mapped_type = OperatorSessionItemType.OTHER
            if item.item_type == WorkspaceItemType.ALERT:
                mapped_type = OperatorSessionItemType.ALERT
            elif item.item_type == WorkspaceItemType.DECISION:
                mapped_type = OperatorSessionItemType.DECISION
            item_specs.append(
                {
                    "item_code": item.item_code,
                    "item_type": mapped_type,
                    "source_ref": item.source_ref,
                    "item_status": OperatorSessionItemStatus.VISIBLE,
                }
            )
        for item in item_specs:
            session_item = OperatorSessionItem(operator_session_id=record.operator_session_id, **item)
            session.add(session_item)
            session.flush()
            append_event_record(
                session,
                deal_id=deal_id,
                event_code="operator_session_item_recorded",
                source_module_id="M-058",
                severity=EventSeverity.INFO,
                payload_json={
                    "operator_session_set_id": session_set.operator_session_set_id,
                    "operator_session_id": record.operator_session_id,
                    "item_code": session_item.item_code,
                    "item_type": session_item.item_type,
                },
            )

        append_event_record(
            session,
            deal_id=deal_id,
            event_code="operator_session_built",
            source_module_id="M-058",
            severity=EventSeverity.INFO,
            payload_json={
                "operator_session_set_id": session_set.operator_session_set_id,
                "operator_session_id": record.operator_session_id,
                "workspace_feed_set_id": workspace_set.workspace_feed_set_id,
                "action_queue_set_id": queue_set.action_queue_set_id,
                "integration_task_set_id": integration_task_set.integration_task_set_id,
                "item_count": len(item_specs),
            },
        )
        session.commit()
        session.refresh(session_set)
        return session_set
    except Exception as exc:
        session_set.session_status = OperatorSessionStatus.STALE
        session_set.updated_at = utcnow()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="operator_session_failed",
            source_module_id="M-058",
            severity=EventSeverity.HIGH,
            payload_json={"operator_session_set_id": session_set.operator_session_set_id, "error": str(exc)},
        )
        session.commit()
        raise


def acknowledge_operator_session_item(
    session: Session,
    payload: AcknowledgeOperatorSessionItemRequest,
) -> OperatorSessionItem:
    session_record = _get_record(session, payload.operator_session_id)
    session_set = _get_set(session, session_record.operator_session_set_id)
    query = select(OperatorSessionItem).where(
        OperatorSessionItem.operator_session_id == payload.operator_session_id,
        OperatorSessionItem.item_code == payload.item_code,
    )
    if payload.source_ref:
        query = query.where(OperatorSessionItem.source_ref == payload.source_ref)
    item = session.scalar(query.order_by(OperatorSessionItem.created_at.asc(), OperatorSessionItem.id.asc()).limit(1))
    if not item:
        raise NotFoundError(
            f"Operator session item '{payload.item_code}' was not found in session '{payload.operator_session_id}'"
        )
    item.item_status = OperatorSessionItemStatus.ACKNOWLEDGED
    item.updated_at = utcnow()
    session_set.updated_at = utcnow()
    session.flush()
    append_event_record(
        session,
        deal_id=resolve_scope_deal_id(session, session_set.scope_type, session_set.scope_ref),
        event_code="operator_session_item_acknowledged",
        source_module_id="M-058",
        severity=EventSeverity.INFO,
        payload_json={
            "operator_session_set_id": session_set.operator_session_set_id,
            "operator_session_id": session_record.operator_session_id,
            "item_code": item.item_code,
            "source_ref": item.source_ref,
        },
    )
    session.commit()
    session.refresh(item)
    return item


def get_operator_session_set(
    session: Session,
    operator_session_set_id: str,
) -> tuple[OperatorSessionSet, list[tuple[OperatorSessionRecord, list[OperatorSessionItem]]]]:
    session_set = _get_set(session, operator_session_set_id)
    records = [get_operator_session_record(session, item.operator_session_id) for item in _get_records(session, operator_session_set_id)]
    return session_set, records


def get_operator_session_record(
    session: Session,
    operator_session_id: str,
) -> tuple[OperatorSessionRecord, list[OperatorSessionItem]]:
    record = _get_record(session, operator_session_id)
    return record, _get_items(session, operator_session_id)


def list_operator_session_sets(
    session: Session,
    *,
    scope_type: str | None = None,
    scope_ref: str | None = None,
) -> list[tuple[OperatorSessionSet, list[tuple[OperatorSessionRecord, list[OperatorSessionItem]]]]]:
    query = select(OperatorSessionSet).order_by(OperatorSessionSet.created_at.desc(), OperatorSessionSet.id.desc())
    if scope_type:
        query = query.where(OperatorSessionSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(OperatorSessionSet.scope_ref == scope_ref)
    sets = list(session.scalars(query))
    return [get_operator_session_set(session, item.operator_session_set_id) for item in sets]
