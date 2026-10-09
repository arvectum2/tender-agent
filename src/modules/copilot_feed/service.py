from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.copilot_feed.models import (
    CopilotFeedItem,
    CopilotFeedRecord,
    CopilotFeedSet,
)
from src.modules.copilot_feed.schemas import BuildCopilotFeedRequest
from src.modules.event_log.service import append_event_record
from src.modules.execution_command.models import ExecutionCommandSet
from src.modules.optimization.models import (
    OptimizationRecommendationRecord,
    OptimizationRecommendationSet,
)
from src.modules.workflow_runs.models import (
    WorkflowRunRecord,
    WorkflowRunSet,
    WorkflowStepRecord,
)
from src.shared.control_package import (
    latest_optimization_context,
    latest_workflow_context,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    CopilotFeedItemType,
    CopilotFeedStatus,
    CopilotPriority,
    EventSeverity,
    OptimizationRecommendationType,
    WorkflowScopeType,
    WorkflowStepStatus,
    WorkflowStepType,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_copilot_feed_id, next_copilot_feed_set_id


def _get_set(session: Session, copilot_feed_set_id: str) -> CopilotFeedSet:
    record = session.scalar(select(CopilotFeedSet).where(CopilotFeedSet.copilot_feed_set_id == copilot_feed_set_id))
    if not record:
        raise NotFoundError(f"Copilot feed set '{copilot_feed_set_id}' was not found")
    return record


def _get_record(session: Session, copilot_feed_id: str) -> CopilotFeedRecord:
    record = session.scalar(select(CopilotFeedRecord).where(CopilotFeedRecord.copilot_feed_id == copilot_feed_id))
    if not record:
        raise NotFoundError(f"Copilot feed record '{copilot_feed_id}' was not found")
    return record


def _get_records(session: Session, copilot_feed_set_id: str) -> list[CopilotFeedRecord]:
    return list(
        session.scalars(
            select(CopilotFeedRecord)
            .where(CopilotFeedRecord.copilot_feed_set_id == copilot_feed_set_id)
            .order_by(CopilotFeedRecord.created_at.asc(), CopilotFeedRecord.id.asc())
        )
    )


def _get_items(session: Session, copilot_feed_id: str) -> list[CopilotFeedItem]:
    return list(
        session.scalars(
            select(CopilotFeedItem)
            .where(CopilotFeedItem.copilot_feed_id == copilot_feed_id)
            .order_by(CopilotFeedItem.created_at.asc(), CopilotFeedItem.id.asc())
        )
    )


def _latest_workflow_context(
    session: Session, scope_type: WorkflowScopeType, scope_ref: str
) -> tuple[WorkflowRunSet | None, WorkflowRunRecord | None, list[WorkflowStepRecord]]:
    # Compatibility name; canonical SQL query lives in shared.control_package.
    return latest_workflow_context(session, scope_type, scope_ref)


def _latest_optimization_context(
    session: Session, scope_type: WorkflowScopeType, scope_ref: str
) -> tuple[OptimizationRecommendationSet | None, list[OptimizationRecommendationRecord], str | None]:
    # Preserve existing callers without maintaining a second query implementation.
    return latest_optimization_context(session, scope_type, scope_ref)


def _feed_item_from_step(step: WorkflowStepRecord) -> tuple[CopilotFeedItemType, CopilotPriority, str]:
    if step.step_status == WorkflowStepStatus.BLOCKED:
        return CopilotFeedItemType.ALERT, CopilotPriority.CRITICAL, f"Блокер: {step.step_code} требует вмешательства."
    if step.step_type == WorkflowStepType.ESCALATE and step.step_status == WorkflowStepStatus.READY:
        return CopilotFeedItemType.ALERT, CopilotPriority.HIGH, f"Эскалировать шаг {step.step_code}."
    if step.step_type == WorkflowStepType.FOLLOW_UP and step.step_status == WorkflowStepStatus.READY:
        return CopilotFeedItemType.FOLLOW_UP, CopilotPriority.MEDIUM, f"Сделать follow-up по шагу {step.step_code}."
    if step.step_status in {WorkflowStepStatus.READY, WorkflowStepStatus.PENDING, WorkflowStepStatus.IN_PROGRESS}:
        return CopilotFeedItemType.ACTION, CopilotPriority.HIGH, f"Выполнить следующий шаг {step.step_code}."
    return CopilotFeedItemType.REMINDER, CopilotPriority.LOW, f"Отслеживать шаг {step.step_code}."


def _priority_from_recommendation(record: OptimizationRecommendationRecord) -> CopilotPriority:
    if record.recommendation_type in {
        OptimizationRecommendationType.RISK_REDUCTION,
        OptimizationRecommendationType.MARGIN,
    }:
        return CopilotPriority.HIGH
    if record.recommendation_type in {
        OptimizationRecommendationType.CYCLE_TIME,
        OptimizationRecommendationType.SUPPLIER_STRATEGY,
    }:
        return CopilotPriority.MEDIUM
    return CopilotPriority.LOW


def build_copilot_feed(session: Session, payload: BuildCopilotFeedRequest) -> CopilotFeedSet:
    feed_set = CopilotFeedSet(
        copilot_feed_set_id=next_copilot_feed_set_id(session, CopilotFeedSet.copilot_feed_set_id),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        feed_status=CopilotFeedStatus.BUILT,
    )
    session.add(feed_set)
    session.flush()
    deal_id_for_event: str | None = payload.scope_ref if payload.scope_type == WorkflowScopeType.DEAL else None
    try:
        workflow_set, workflow_record, workflow_steps = _latest_workflow_context(session, payload.scope_type, payload.scope_ref)
        if not workflow_set or not workflow_record:
            raise ValidationError("Copilot feed requires persisted workflow run context")
        optimization_set, optimization_records, optimization_scope_ref = _latest_optimization_context(
            session, payload.scope_type, payload.scope_ref
        )
        if not optimization_set:
            raise ValidationError("Copilot feed requires persisted optimization context")

        if payload.scope_type == WorkflowScopeType.EXECUTION and not deal_id_for_event:
            execution_set = session.scalar(
                select(ExecutionCommandSet).where(ExecutionCommandSet.execution_command_set_id == payload.scope_ref)
            )
            deal_id_for_event = execution_set.deal_id if execution_set else None

        actionable_steps = [
            step
            for step in workflow_steps
            if step.step_status in {WorkflowStepStatus.READY, WorkflowStepStatus.PENDING, WorkflowStepStatus.BLOCKED}
        ]
        optimization_action_records = [
            record for record in optimization_records if record.recommendation_code != "OPTIMIZATION_SUMMARY"
        ]

        summary = (
            f"Copilot feed for {payload.scope_type}:{payload.scope_ref}: "
            f"workflow_steps={len(actionable_steps)}, recommendations={len(optimization_action_records)}."
        )
        record = CopilotFeedRecord(
            copilot_feed_id=next_copilot_feed_id(session, CopilotFeedRecord.copilot_feed_id),
            copilot_feed_set_id=feed_set.copilot_feed_set_id,
            summary_text=summary,
        )
        session.add(record)
        session.flush()

        item_specs: list[dict] = []
        for step in actionable_steps:
            item_type, priority, text = _feed_item_from_step(step)
            item_specs.append(
                {
                    "item_code": step.step_code,
                    "item_type": item_type,
                    "priority": priority,
                    "item_text": text,
                    "source_ref": step.workflow_step_id,
                }
            )
        for recommendation in optimization_action_records:
            item_specs.append(
                {
                    "item_code": recommendation.recommendation_code,
                    "item_type": CopilotFeedItemType.RECOMMENDATION,
                    "priority": _priority_from_recommendation(recommendation),
                    "item_text": recommendation.recommendation_text,
                    "source_ref": recommendation.optimization_recommendation_id,
                }
            )
        if not item_specs:
            item_specs.append(
                {
                    "item_code": "MONITOR_ONLY",
                    "item_type": CopilotFeedItemType.REMINDER,
                    "priority": CopilotPriority.LOW,
                    "item_text": "Активных operator actions не обнаружено, оставить контур в monitoring mode.",
                    "source_ref": workflow_set.workflow_run_set_id,
                }
            )

        for item in item_specs:
            feed_item = CopilotFeedItem(copilot_feed_id=record.copilot_feed_id, **item)
            session.add(feed_item)
            session.flush()
            append_event_record(
                session,
                deal_id=deal_id_for_event,
                event_code="copilot_feed_item_recorded",
                source_module_id="M-053",
                severity=EventSeverity.INFO,
                payload_json={
                    "copilot_feed_set_id": feed_set.copilot_feed_set_id,
                    "copilot_feed_id": record.copilot_feed_id,
                    "item_code": feed_item.item_code,
                    "priority": feed_item.priority,
                },
            )

        feed_set.updated_at = utcnow()
        session.add(feed_set)
        append_event_record(
            session,
            deal_id=deal_id_for_event,
            event_code="copilot_feed_built",
            source_module_id="M-053",
            severity=EventSeverity.INFO,
            payload_json={
                "copilot_feed_set_id": feed_set.copilot_feed_set_id,
                "copilot_feed_id": record.copilot_feed_id,
                "scope_type": str(payload.scope_type),
                "scope_ref": payload.scope_ref,
                "workflow_run_set_id": workflow_set.workflow_run_set_id,
                "optimization_recommendation_set_id": optimization_set.optimization_recommendation_set_id,
                "item_count": len(item_specs),
                "optimization_scope_ref": optimization_scope_ref,
            },
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        failed_set = CopilotFeedSet(
            copilot_feed_set_id=feed_set.copilot_feed_set_id,
            scope_type=payload.scope_type,
            scope_ref=payload.scope_ref,
            feed_status=CopilotFeedStatus.FAILED,
        )
        session.add(failed_set)
        append_event_record(
            session,
            deal_id=deal_id_for_event,
            event_code="copilot_feed_failed",
            source_module_id="M-053",
            severity=EventSeverity.HIGH,
            payload_json={"copilot_feed_set_id": feed_set.copilot_feed_set_id, "error": str(exc)},
        )
        session.commit()
        raise
    session.refresh(feed_set)
    return feed_set


def get_copilot_feed_set(
    session: Session, copilot_feed_set_id: str
) -> tuple[CopilotFeedSet, list[tuple[CopilotFeedRecord, list[CopilotFeedItem]]]]:
    feed_set = _get_set(session, copilot_feed_set_id)
    records = _get_records(session, copilot_feed_set_id)
    return feed_set, [(record, _get_items(session, record.copilot_feed_id)) for record in records]


def list_copilot_feed_sets(
    session: Session,
    *,
    scope_type: WorkflowScopeType | None = None,
    scope_ref: str | None = None,
) -> list[tuple[CopilotFeedSet, list[tuple[CopilotFeedRecord, list[CopilotFeedItem]]]]]:
    query = select(CopilotFeedSet).order_by(CopilotFeedSet.created_at.desc(), CopilotFeedSet.id.desc())
    if scope_type:
        query = query.where(CopilotFeedSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(CopilotFeedSet.scope_ref == scope_ref)
    sets = list(session.scalars(query))
    return [get_copilot_feed_set(session, item.copilot_feed_set_id) for item in sets]


def get_copilot_feed_record(session: Session, copilot_feed_id: str) -> tuple[CopilotFeedRecord, list[CopilotFeedItem]]:
    record = _get_record(session, copilot_feed_id)
    return record, _get_items(session, copilot_feed_id)
