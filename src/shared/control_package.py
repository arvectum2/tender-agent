from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.action_queue.models import (
    ActionQueueApproval,
    ActionQueueRecord,
    ActionQueueSet,
)
from src.modules.connector_registry.models import (
    ConnectorRegistryRecord,
    ConnectorRegistrySet,
)
from src.modules.copilot_feed.models import (
    CopilotFeedItem,
    CopilotFeedRecord,
    CopilotFeedSet,
)
from src.modules.deal_registry.models import Deal
from src.modules.execution_command.models import ExecutionCommandSet
from src.modules.execution_ledger.models import (
    ExecutionLedgerRecord,
    ExecutionLedgerSet,
    ExecutionResultRecord,
)
from src.modules.integration_tasks.models import (
    IntegrationTaskRecord,
    IntegrationTaskSet,
)
from src.modules.operator_sessions.models import (
    OperatorSessionItem,
    OperatorSessionRecord,
    OperatorSessionSet,
)
from src.modules.optimization.models import (
    OptimizationRecommendationRecord,
    OptimizationRecommendationSet,
)
from src.modules.workflow_runs.models import (
    WorkflowRunRecord,
    WorkflowRunSet,
    WorkflowStepRecord,
)
from src.modules.workspace_feed.models import (
    WorkspaceFeedItem,
    WorkspaceFeedRecord,
    WorkspaceFeedSet,
)
from src.shared.enums import OptimizationScopeType, WorkflowScopeType
from src.shared.errors import NotFoundError


def latest_integration_task_set(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[IntegrationTaskSet | None, list[IntegrationTaskRecord]]:
    """Single canonical query shared by ledger, execution and operator sessions."""
    task_set = session.scalar(
        select(IntegrationTaskSet)
        .where(IntegrationTaskSet.scope_type == scope_type, IntegrationTaskSet.scope_ref == scope_ref)
        .order_by(IntegrationTaskSet.created_at.desc(), IntegrationTaskSet.id.desc())
        .limit(1)
    )
    if not task_set:
        return None, []
    records = list(
        session.scalars(
            select(IntegrationTaskRecord)
            .where(IntegrationTaskRecord.integration_task_set_id == task_set.integration_task_set_id)
            .order_by(IntegrationTaskRecord.created_at.asc(), IntegrationTaskRecord.id.asc())
        )
    )
    return task_set, records

def ensure_scope_exists(session: Session, scope_type: str, scope_ref: str) -> None:
    if scope_type == WorkflowScopeType.DEAL:
        deal = session.scalar(select(Deal).where(Deal.deal_id == scope_ref, Deal.is_deleted.is_(False)))
        if not deal:
            raise NotFoundError(f"Deal '{scope_ref}' was not found")
    elif scope_type == WorkflowScopeType.EXECUTION:
        execution_set = session.scalar(
            select(ExecutionCommandSet).where(ExecutionCommandSet.execution_command_set_id == scope_ref)
        )
        if not execution_set:
            raise NotFoundError(f"Execution command set '{scope_ref}' was not found")


def resolve_scope_deal_id(session: Session, scope_type: str, scope_ref: str) -> str | None:
    if scope_type == WorkflowScopeType.DEAL:
        return scope_ref
    if scope_type == WorkflowScopeType.EXECUTION:
        execution_set = session.scalar(
            select(ExecutionCommandSet).where(ExecutionCommandSet.execution_command_set_id == scope_ref)
        )
        return execution_set.deal_id if execution_set else None
    return None


def latest_workflow_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[WorkflowRunSet | None, WorkflowRunRecord | None, list[WorkflowStepRecord]]:
    workflow_set = session.scalar(
        select(WorkflowRunSet)
        .where(WorkflowRunSet.scope_type == scope_type, WorkflowRunSet.scope_ref == scope_ref)
        .order_by(WorkflowRunSet.created_at.desc(), WorkflowRunSet.id.desc())
        .limit(1)
    )
    if not workflow_set:
        return None, None, []
    workflow_record = session.scalar(
        select(WorkflowRunRecord)
        .where(WorkflowRunRecord.workflow_run_set_id == workflow_set.workflow_run_set_id)
        .order_by(WorkflowRunRecord.created_at.desc(), WorkflowRunRecord.id.desc())
        .limit(1)
    )
    if not workflow_record:
        return workflow_set, None, []
    steps = list(
        session.scalars(
            select(WorkflowStepRecord)
            .where(WorkflowStepRecord.workflow_run_id == workflow_record.workflow_run_id)
            .order_by(WorkflowStepRecord.created_at.asc(), WorkflowStepRecord.id.asc())
        )
    )
    return workflow_set, workflow_record, steps


def latest_optimization_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[OptimizationRecommendationSet | None, list[OptimizationRecommendationRecord], str | None]:
    candidates: list[tuple[OptimizationScopeType, str]] = []
    if scope_type == WorkflowScopeType.DEAL:
        candidates.append((OptimizationScopeType.DEAL, scope_ref))
    elif scope_type == WorkflowScopeType.PORTFOLIO:
        candidates.append((OptimizationScopeType.PORTFOLIO, scope_ref))
        candidates.append((OptimizationScopeType.PROCESS, scope_ref))
    elif scope_type == WorkflowScopeType.PIPELINE:
        candidates.append((OptimizationScopeType.PROCESS, scope_ref))
        candidates.append((OptimizationScopeType.PORTFOLIO, "GLOBAL"))
    else:
        candidates.append((OptimizationScopeType.PROCESS, scope_ref))
        execution_set = session.scalar(
            select(ExecutionCommandSet).where(ExecutionCommandSet.execution_command_set_id == scope_ref)
        )
        if execution_set:
            candidates.append((OptimizationScopeType.DEAL, execution_set.deal_id))

    for optimization_scope, candidate_ref in candidates:
        optimization_set = session.scalar(
            select(OptimizationRecommendationSet)
            .where(
                OptimizationRecommendationSet.scope_type == optimization_scope,
                OptimizationRecommendationSet.scope_ref == candidate_ref,
            )
            .order_by(
                OptimizationRecommendationSet.created_at.desc(),
                OptimizationRecommendationSet.id.desc(),
            )
            .limit(1)
        )
        if optimization_set:
            records = list(
                session.scalars(
                    select(OptimizationRecommendationRecord)
                    .where(
                        OptimizationRecommendationRecord.optimization_recommendation_set_id
                        == optimization_set.optimization_recommendation_set_id
                    )
                    .order_by(
                        OptimizationRecommendationRecord.created_at.asc(),
                        OptimizationRecommendationRecord.id.asc(),
                    )
                )
            )
            return optimization_set, records, candidate_ref
    return None, [], None


def latest_copilot_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[CopilotFeedSet | None, CopilotFeedRecord | None, list[CopilotFeedItem]]:
    feed_set = session.scalar(
        select(CopilotFeedSet)
        .where(CopilotFeedSet.scope_type == scope_type, CopilotFeedSet.scope_ref == scope_ref)
        .order_by(CopilotFeedSet.created_at.desc(), CopilotFeedSet.id.desc())
        .limit(1)
    )
    if not feed_set:
        return None, None, []
    feed_record = session.scalar(
        select(CopilotFeedRecord)
        .where(CopilotFeedRecord.copilot_feed_set_id == feed_set.copilot_feed_set_id)
        .order_by(CopilotFeedRecord.created_at.desc(), CopilotFeedRecord.id.desc())
        .limit(1)
    )
    if not feed_record:
        return feed_set, None, []
    items = list(
        session.scalars(
            select(CopilotFeedItem)
            .where(CopilotFeedItem.copilot_feed_id == feed_record.copilot_feed_id)
            .order_by(CopilotFeedItem.created_at.asc(), CopilotFeedItem.id.asc())
        )
    )
    return feed_set, feed_record, items


def latest_workspace_feed_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[WorkspaceFeedSet | None, WorkspaceFeedRecord | None, list[WorkspaceFeedItem]]:
    feed_set = session.scalar(
        select(WorkspaceFeedSet)
        .where(WorkspaceFeedSet.scope_type == scope_type, WorkspaceFeedSet.scope_ref == scope_ref)
        .order_by(WorkspaceFeedSet.created_at.desc(), WorkspaceFeedSet.id.desc())
        .limit(1)
    )
    if not feed_set:
        return None, None, []
    feed_record = session.scalar(
        select(WorkspaceFeedRecord)
        .where(WorkspaceFeedRecord.workspace_feed_set_id == feed_set.workspace_feed_set_id)
        .order_by(WorkspaceFeedRecord.created_at.desc(), WorkspaceFeedRecord.id.desc())
        .limit(1)
    )
    if not feed_record:
        return feed_set, None, []
    items = list(
        session.scalars(
            select(WorkspaceFeedItem)
            .where(WorkspaceFeedItem.workspace_feed_id == feed_record.workspace_feed_id)
            .order_by(WorkspaceFeedItem.created_at.asc(), WorkspaceFeedItem.id.asc())
        )
    )
    return feed_set, feed_record, items


def latest_connector_registry_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[ConnectorRegistrySet | None, list[ConnectorRegistryRecord]]:
    registry_set = session.scalar(
        select(ConnectorRegistrySet)
        .where(ConnectorRegistrySet.scope_type == scope_type, ConnectorRegistrySet.scope_ref == scope_ref)
        .order_by(ConnectorRegistrySet.created_at.desc(), ConnectorRegistrySet.id.desc())
        .limit(1)
    )
    if not registry_set:
        return None, []
    records = list(
        session.scalars(
            select(ConnectorRegistryRecord)
            .where(ConnectorRegistryRecord.connector_registry_set_id == registry_set.connector_registry_set_id)
            .order_by(ConnectorRegistryRecord.created_at.asc(), ConnectorRegistryRecord.id.asc())
        )
    )
    return registry_set, records


def latest_action_queue_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[ActionQueueSet | None, list[tuple[ActionQueueRecord, list[ActionQueueApproval]]]]:
    queue_set = session.scalar(
        select(ActionQueueSet)
        .where(ActionQueueSet.scope_type == scope_type, ActionQueueSet.scope_ref == scope_ref)
        .order_by(ActionQueueSet.created_at.desc(), ActionQueueSet.id.desc())
        .limit(1)
    )
    if not queue_set:
        return None, []
    records = list(
        session.scalars(
            select(ActionQueueRecord)
            .where(ActionQueueRecord.action_queue_set_id == queue_set.action_queue_set_id)
            .order_by(ActionQueueRecord.created_at.asc(), ActionQueueRecord.id.asc())
        )
    )
    result: list[tuple[ActionQueueRecord, list[ActionQueueApproval]]] = []
    for record in records:
        approvals = list(
            session.scalars(
                select(ActionQueueApproval)
                .where(ActionQueueApproval.action_queue_id == record.action_queue_id)
                .order_by(ActionQueueApproval.created_at.asc(), ActionQueueApproval.id.asc())
            )
        )
        result.append((record, approvals))
    return queue_set, result


def latest_operator_session_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[OperatorSessionSet | None, OperatorSessionRecord | None, list[OperatorSessionItem]]:
    session_set = session.scalar(
        select(OperatorSessionSet)
        .where(OperatorSessionSet.scope_type == scope_type, OperatorSessionSet.scope_ref == scope_ref)
        .order_by(OperatorSessionSet.created_at.desc(), OperatorSessionSet.id.desc())
        .limit(1)
    )
    if not session_set:
        return None, None, []
    session_record = session.scalar(
        select(OperatorSessionRecord)
        .where(OperatorSessionRecord.operator_session_set_id == session_set.operator_session_set_id)
        .order_by(OperatorSessionRecord.created_at.desc(), OperatorSessionRecord.id.desc())
        .limit(1)
    )
    if not session_record:
        return session_set, None, []
    items = list(
        session.scalars(
            select(OperatorSessionItem)
            .where(OperatorSessionItem.operator_session_id == session_record.operator_session_id)
            .order_by(OperatorSessionItem.created_at.asc(), OperatorSessionItem.id.asc())
        )
    )
    return session_set, session_record, items


def latest_execution_ledger_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[ExecutionLedgerSet | None, list[tuple[ExecutionLedgerRecord, list[ExecutionResultRecord]]]]:
    ledger_set = session.scalar(
        select(ExecutionLedgerSet)
        .where(ExecutionLedgerSet.scope_type == scope_type, ExecutionLedgerSet.scope_ref == scope_ref)
        .order_by(ExecutionLedgerSet.created_at.desc(), ExecutionLedgerSet.id.desc())
        .limit(1)
    )
    if not ledger_set:
        return None, []
    records = list(
        session.scalars(
            select(ExecutionLedgerRecord)
            .where(ExecutionLedgerRecord.execution_ledger_set_id == ledger_set.execution_ledger_set_id)
            .order_by(ExecutionLedgerRecord.created_at.asc(), ExecutionLedgerRecord.id.asc())
        )
    )
    result: list[tuple[ExecutionLedgerRecord, list[ExecutionResultRecord]]] = []
    for record in records:
        results = list(
            session.scalars(
                select(ExecutionResultRecord)
                .where(ExecutionResultRecord.execution_ledger_id == record.execution_ledger_id)
                .order_by(ExecutionResultRecord.created_at.asc(), ExecutionResultRecord.id.asc())
            )
        )
        result.append((record, results))
    return ledger_set, result
