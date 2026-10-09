from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.action_queue.models import (
    ActionQueueApproval,
    ActionQueueRecord,
    ActionQueueSet,
)
from src.modules.action_queue.schemas import (
    ApproveActionQueueItemRequest,
    BuildActionQueueRequest,
)
from src.modules.event_log.service import append_event_record
from src.modules.workspace_feed.models import (
    WorkspaceFeedItem,
    WorkspaceFeedRecord,
    WorkspaceFeedSet,
)
from src.shared.control_package import (
    ensure_scope_exists,
    latest_workspace_feed_context,
    resolve_scope_deal_id,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    ActionExecutionStatus,
    ActionQueueStatus,
    ActionType,
    EventSeverity,
    QueueApprovalStatus,
    WorkspaceItemType,
    WorkspacePriority,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_action_queue_id, next_action_queue_set_id
from src.shared.validation import require_non_empty


def _get_set(session: Session, action_queue_set_id: str) -> ActionQueueSet:
    record = session.scalar(select(ActionQueueSet).where(ActionQueueSet.action_queue_set_id == action_queue_set_id))
    if not record:
        raise NotFoundError(f"Action queue set '{action_queue_set_id}' was not found")
    return record


def _get_record(session: Session, action_queue_id: str) -> ActionQueueRecord:
    record = session.scalar(select(ActionQueueRecord).where(ActionQueueRecord.action_queue_id == action_queue_id))
    if not record:
        raise NotFoundError(f"Action queue record '{action_queue_id}' was not found")
    return record


def _get_records(session: Session, action_queue_set_id: str) -> list[ActionQueueRecord]:
    return list(
        session.scalars(
            select(ActionQueueRecord)
            .where(ActionQueueRecord.action_queue_set_id == action_queue_set_id)
            .order_by(ActionQueueRecord.created_at.asc(), ActionQueueRecord.id.asc())
        )
    )


def _get_approvals(session: Session, action_queue_id: str) -> list[ActionQueueApproval]:
    return list(
        session.scalars(
            select(ActionQueueApproval)
            .where(ActionQueueApproval.action_queue_id == action_queue_id)
            .order_by(ActionQueueApproval.created_at.asc(), ActionQueueApproval.id.asc())
        )
    )


def _latest_workspace_feed(
    session: Session, scope_type: str, scope_ref: str
) -> tuple[WorkspaceFeedSet | None, WorkspaceFeedRecord | None, list[WorkspaceFeedItem]]:
    # Compatibility name; one canonical source of query semantics.
    return latest_workspace_feed_context(session, scope_type, scope_ref)


def _action_type_from_workspace_item(item: WorkspaceFeedItem) -> ActionType:
    if item.item_type == WorkspaceItemType.FOLLOW_UP:
        return ActionType.FOLLOW_UP
    if item.item_type == WorkspaceItemType.ALERT:
        return ActionType.ESCALATE
    if item.item_type == WorkspaceItemType.TASK:
        return ActionType.REBUILD
    if item.item_type == WorkspaceItemType.DECISION:
        return ActionType.ESCALATE
    if item.item_type == WorkspaceItemType.SUGGESTION:
        return ActionType.REBUILD
    return ActionType.OTHER


def _should_queue(item: WorkspaceFeedItem) -> bool:
    return item.priority in {
        WorkspacePriority.HIGH,
        WorkspacePriority.CRITICAL,
    } or item.item_type in {
        WorkspaceItemType.FOLLOW_UP,
        WorkspaceItemType.ALERT,
        WorkspaceItemType.DECISION,
    }


def build_action_queue(session: Session, payload: BuildActionQueueRequest) -> ActionQueueSet:
    ensure_scope_exists(session, payload.scope_type, payload.scope_ref)
    queue_set = ActionQueueSet(
        action_queue_set_id=next_action_queue_set_id(session, ActionQueueSet.action_queue_set_id),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        queue_status=ActionQueueStatus.BUILT,
    )
    session.add(queue_set)
    session.flush()
    deal_id = resolve_scope_deal_id(session, payload.scope_type, payload.scope_ref)
    try:
        workspace_set, workspace_record, workspace_items = _latest_workspace_feed(
            session, payload.scope_type, payload.scope_ref
        )
        if not workspace_set or not workspace_record:
            raise ValidationError("Action queue requires persisted workspace feed context")

        queued_items = [item for item in workspace_items if _should_queue(item)]
        if not queued_items and workspace_items:
            queued_items = workspace_items[:1]

        for item in queued_items:
            action_record = ActionQueueRecord(
                action_queue_id=next_action_queue_id(session, ActionQueueRecord.action_queue_id),
                action_queue_set_id=queue_set.action_queue_set_id,
                action_code=item.item_code,
                action_type=_action_type_from_workspace_item(item),
                action_status=ActionExecutionStatus.PENDING,
                action_text=item.item_text,
                source_ref=item.source_ref,
            )
            session.add(action_record)
            session.flush()
            append_event_record(
                session,
                deal_id=deal_id,
                event_code="action_queue_item_recorded",
                source_module_id="M-056",
                severity=EventSeverity.INFO,
                payload_json={
                    "action_queue_set_id": queue_set.action_queue_set_id,
                    "action_queue_id": action_record.action_queue_id,
                    "action_code": action_record.action_code,
                    "action_type": action_record.action_type,
                },
            )

        queue_set.queue_status = ActionQueueStatus.ACTIVE if queued_items else ActionQueueStatus.BUILT
        queue_set.updated_at = utcnow()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="action_queue_built",
            source_module_id="M-056",
            severity=EventSeverity.INFO,
            payload_json={
                "action_queue_set_id": queue_set.action_queue_set_id,
                "item_count": len(queued_items),
                "workspace_feed_set_id": workspace_set.workspace_feed_set_id,
            },
        )
        session.commit()
        session.refresh(queue_set)
        return queue_set
    except Exception as exc:
        queue_set.queue_status = ActionQueueStatus.FAILED
        queue_set.updated_at = utcnow()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="action_queue_failed",
            source_module_id="M-056",
            severity=EventSeverity.HIGH,
            payload_json={"error": str(exc)},
        )
        session.commit()
        raise


def approve_action_queue_item(session: Session, payload: ApproveActionQueueItemRequest) -> ActionQueueApproval:
    action_record = _get_record(session, payload.action_queue_id)
    queue_set = _get_set(session, action_record.action_queue_set_id)
    deal_id = resolve_scope_deal_id(session, queue_set.scope_type, queue_set.scope_ref)
    approval = ActionQueueApproval(
        action_queue_id=action_record.action_queue_id,
        approval_status=payload.approval_status,
        approved_by_ref=require_non_empty(payload.approved_by_ref, "approved_by_ref"),
        rationale=require_non_empty(payload.rationale, "rationale"),
    )
    session.add(approval)
    if payload.approval_status == QueueApprovalStatus.APPROVED:
        action_record.action_status = ActionExecutionStatus.APPROVED
        event_code = "action_queue_approved"
    elif payload.approval_status == QueueApprovalStatus.REJECTED:
        action_record.action_status = ActionExecutionStatus.REJECTED
        event_code = "action_queue_rejected"
    else:
        action_record.action_status = ActionExecutionStatus.PENDING
        event_code = None
    action_record.updated_at = utcnow()
    queue_set.updated_at = utcnow()
    session.flush()
    if event_code:
        append_event_record(
            session,
            deal_id=deal_id,
            event_code=event_code,
            source_module_id="M-056",
            severity=EventSeverity.INFO,
            payload_json={
                "action_queue_set_id": queue_set.action_queue_set_id,
                "action_queue_id": action_record.action_queue_id,
                "approval_status": payload.approval_status,
                "approved_by_ref": approval.approved_by_ref,
            },
        )
    session.commit()
    session.refresh(approval)
    return approval


def get_action_queue_set(
    session: Session,
    action_queue_set_id: str,
) -> tuple[ActionQueueSet, list[tuple[ActionQueueRecord, list[ActionQueueApproval]]]]:
    queue_set = _get_set(session, action_queue_set_id)
    records = [get_action_queue_record(session, item.action_queue_id) for item in _get_records(session, action_queue_set_id)]
    return queue_set, records


def get_action_queue_record(
    session: Session,
    action_queue_id: str,
) -> tuple[ActionQueueRecord, list[ActionQueueApproval]]:
    record = _get_record(session, action_queue_id)
    return record, _get_approvals(session, action_queue_id)


def list_action_queue_sets(
    session: Session,
    *,
    scope_type: str | None = None,
    scope_ref: str | None = None,
) -> list[tuple[ActionQueueSet, list[tuple[ActionQueueRecord, list[ActionQueueApproval]]]]]:
    query = select(ActionQueueSet).order_by(ActionQueueSet.created_at.desc(), ActionQueueSet.id.desc())
    if scope_type:
        query = query.where(ActionQueueSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(ActionQueueSet.scope_ref == scope_ref)
    sets = list(session.scalars(query))
    return [get_action_queue_set(session, item.action_queue_set_id) for item in sets]
