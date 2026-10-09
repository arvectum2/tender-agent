from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.action_queue.models import ActionQueueRecord
from src.modules.connector_registry.models import ConnectorRegistryRecord
from src.modules.event_log.service import append_event_record
from src.modules.execution_ledger.models import (
    ExecutionLedgerRecord,
    ExecutionLedgerSet,
    ExecutionResultRecord,
)
from src.modules.execution_ledger.schemas import (
    BuildExecutionLedgerRequest,
    StartExecutionLedgerRequest,
)
from src.modules.integration_tasks.models import (
    IntegrationTaskRecord,
    IntegrationTaskSet,
)
from src.shared.control_package import (
    ensure_scope_exists,
    latest_action_queue_context,
    latest_integration_task_set,
    resolve_scope_deal_id,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    ActionExecutionStatus,
    ConnectorStatus,
    EventSeverity,
    ExecutionLedgerStatus,
    ExecutionStatus,
    QueueApprovalStatus,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_execution_ledger_id, next_execution_ledger_set_id


def _get_set(session: Session, execution_ledger_set_id: str) -> ExecutionLedgerSet:
    record = session.scalar(
        select(ExecutionLedgerSet).where(ExecutionLedgerSet.execution_ledger_set_id == execution_ledger_set_id)
    )
    if not record:
        raise NotFoundError(f"Execution ledger set '{execution_ledger_set_id}' was not found")
    return record


def _get_record(session: Session, execution_ledger_id: str) -> ExecutionLedgerRecord:
    record = session.scalar(
        select(ExecutionLedgerRecord).where(ExecutionLedgerRecord.execution_ledger_id == execution_ledger_id)
    )
    if not record:
        raise NotFoundError(f"Execution ledger record '{execution_ledger_id}' was not found")
    return record


def _get_records(session: Session, execution_ledger_set_id: str) -> list[ExecutionLedgerRecord]:
    return list(
        session.scalars(
            select(ExecutionLedgerRecord)
            .where(ExecutionLedgerRecord.execution_ledger_set_id == execution_ledger_set_id)
            .order_by(ExecutionLedgerRecord.created_at.asc(), ExecutionLedgerRecord.id.asc())
        )
    )


def _get_results(session: Session, execution_ledger_id: str) -> list[ExecutionResultRecord]:
    return list(
        session.scalars(
            select(ExecutionResultRecord)
            .where(ExecutionResultRecord.execution_ledger_id == execution_ledger_id)
            .order_by(ExecutionResultRecord.created_at.asc(), ExecutionResultRecord.id.asc())
        )
    )


def _latest_integration_task_set(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[IntegrationTaskSet | None, list[IntegrationTaskRecord]]:
    # Historical private name kept for call sites and monkeypatchable tests.
    return latest_integration_task_set(session, scope_type, scope_ref)

def _latest_approval_is_approved(session: Session, action_queue_id: str) -> bool:
    from src.modules.action_queue.models import ActionQueueApproval

    approval = session.scalar(
        select(ActionQueueApproval)
        .where(ActionQueueApproval.action_queue_id == action_queue_id)
        .order_by(ActionQueueApproval.created_at.desc(), ActionQueueApproval.id.desc())
        .limit(1)
    )
    return approval is not None and str(approval.approval_status) == str(QueueApprovalStatus.APPROVED)


def build_execution_ledger(session: Session, payload: BuildExecutionLedgerRequest) -> ExecutionLedgerSet:
    ensure_scope_exists(session, payload.scope_type, payload.scope_ref)
    ledger_set = ExecutionLedgerSet(
        execution_ledger_set_id=next_execution_ledger_set_id(session, ExecutionLedgerSet.execution_ledger_set_id),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        ledger_status=ExecutionLedgerStatus.BUILT,
    )
    session.add(ledger_set)
    session.flush()
    deal_id = resolve_scope_deal_id(session, payload.scope_type, payload.scope_ref)
    try:
        task_set, tasks = _latest_integration_task_set(session, payload.scope_type, payload.scope_ref)
        queue_set, queue_records = latest_action_queue_context(session, payload.scope_type, payload.scope_ref)
        if not task_set or not tasks:
            raise ValidationError("Execution ledger requires persisted integration tasks")
        if not queue_set or not queue_records:
            raise ValidationError("Execution ledger requires persisted action queue context")

        approved_action_ids = {
            record.action_queue_id
            for record, _approvals in queue_records
            if str(record.action_status) == str(ActionExecutionStatus.APPROVED) and _latest_approval_is_approved(session, record.action_queue_id)
        }
        eligible_tasks = [task for task in tasks if task.action_queue_id in approved_action_ids]
        if not eligible_tasks:
            raise ValidationError("Execution ledger requires approved integration task candidates")

        for task in eligible_tasks:
            session.add(
                ExecutionLedgerRecord(
                    execution_ledger_id=next_execution_ledger_id(session, ExecutionLedgerRecord.execution_ledger_id),
                    execution_ledger_set_id=ledger_set.execution_ledger_set_id,
                    action_queue_id=task.action_queue_id,
                    integration_task_id=task.integration_task_id,
                    execution_status=ExecutionStatus.STARTED,
                    started_at=None,
                    finished_at=None,
                )
            )
            session.flush()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="execution_ledger_built",
            source_module_id="M-059",
            severity=EventSeverity.INFO,
            payload_json={
                "execution_ledger_set_id": ledger_set.execution_ledger_set_id,
                "integration_task_set_id": task_set.integration_task_set_id,
                "action_queue_set_id": queue_set.action_queue_set_id,
                "candidate_count": len(eligible_tasks),
            },
        )
        session.commit()
        session.refresh(ledger_set)
        return ledger_set
    except Exception as exc:
        ledger_set.ledger_status = ExecutionLedgerStatus.FAILED
        ledger_set.updated_at = utcnow()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="execution_ledger_failed",
            source_module_id="M-059",
            severity=EventSeverity.HIGH,
            payload_json={"execution_ledger_set_id": ledger_set.execution_ledger_set_id, "error": str(exc)},
        )
        session.commit()
        raise


def start_execution_ledger(session: Session, payload: StartExecutionLedgerRequest) -> ExecutionLedgerRecord:
    record = _get_record(session, payload.execution_ledger_id)
    ledger_set = _get_set(session, record.execution_ledger_set_id)
    deal_id = resolve_scope_deal_id(session, ledger_set.scope_type, ledger_set.scope_ref)
    action_queue_record = session.scalar(
        select(ActionQueueRecord).where(ActionQueueRecord.action_queue_id == record.action_queue_id)
    )
    integration_task = session.scalar(
        select(IntegrationTaskRecord).where(IntegrationTaskRecord.integration_task_id == record.integration_task_id)
    )
    if not action_queue_record or not integration_task:
        raise ValidationError("Execution ledger record requires persisted action queue and integration task context")
    if str(action_queue_record.action_status) != str(ActionExecutionStatus.APPROVED) or not _latest_approval_is_approved(
        session, action_queue_record.action_queue_id
    ):
        raise ValidationError("Execution start requires approved action queue item")
    if record.started_at is not None:
        raise ValidationError("Execution ledger record is already started")

    connector = session.scalar(
        select(ConnectorRegistryRecord).where(
            ConnectorRegistryRecord.connector_registry_id == integration_task.connector_registry_id
        )
    )
    if not connector:
        raise ValidationError("Execution ledger record requires persisted connector context")

    record.started_at = utcnow()
    record.updated_at = utcnow()
    ledger_set.ledger_status = ExecutionLedgerStatus.ACTIVE
    ledger_set.updated_at = utcnow()
    append_event_record(
        session,
        deal_id=deal_id,
        event_code="execution_ledger_started",
        source_module_id="M-059",
        severity=EventSeverity.INFO,
        payload_json={
            "execution_ledger_set_id": ledger_set.execution_ledger_set_id,
            "execution_ledger_id": record.execution_ledger_id,
            "action_queue_id": record.action_queue_id,
            "executed_by_ref": payload.executed_by_ref,
        },
    )

    if str(connector.connector_status) == str(ConnectorStatus.ACTIVE):
        record.execution_status = ExecutionStatus.SUCCEEDED
        result = ExecutionResultRecord(
            execution_ledger_id=record.execution_ledger_id,
            result_code="EXECUTION_OK",
            result_summary=f"Execution succeeded via connector {connector.connector_code}.",
            artifact_ref=None,
        )
        event_code = "execution_ledger_succeeded"
        severity = EventSeverity.INFO
        ledger_set.ledger_status = ExecutionLedgerStatus.ACTIVE
    else:
        record.execution_status = ExecutionStatus.FAILED
        result = ExecutionResultRecord(
            execution_ledger_id=record.execution_ledger_id,
            result_code="CONNECTOR_UNAVAILABLE",
            result_summary=f"Execution failed because connector {connector.connector_code} is not ACTIVE.",
            artifact_ref=None,
        )
        event_code = "execution_ledger_failed"
        severity = EventSeverity.HIGH
        ledger_set.ledger_status = ExecutionLedgerStatus.FAILED
    record.finished_at = utcnow()
    session.add(result)
    session.flush()
    append_event_record(
        session,
        deal_id=deal_id,
        event_code=event_code,
        source_module_id="M-059",
        severity=severity,
        payload_json={
            "execution_ledger_set_id": ledger_set.execution_ledger_set_id,
            "execution_ledger_id": record.execution_ledger_id,
            "result_code": result.result_code,
        },
    )
    session.commit()
    session.refresh(record)
    return record


def get_execution_ledger_set(
    session: Session,
    execution_ledger_set_id: str,
) -> tuple[ExecutionLedgerSet, list[tuple[ExecutionLedgerRecord, list[ExecutionResultRecord]]]]:
    ledger_set = _get_set(session, execution_ledger_set_id)
    records = [get_execution_ledger_record(session, item.execution_ledger_id) for item in _get_records(session, execution_ledger_set_id)]
    return ledger_set, records


def get_execution_ledger_record(
    session: Session,
    execution_ledger_id: str,
) -> tuple[ExecutionLedgerRecord, list[ExecutionResultRecord]]:
    record = _get_record(session, execution_ledger_id)
    return record, _get_results(session, execution_ledger_id)


def list_execution_ledger_sets(
    session: Session,
    *,
    scope_type: str | None = None,
    scope_ref: str | None = None,
) -> list[tuple[ExecutionLedgerSet, list[tuple[ExecutionLedgerRecord, list[ExecutionResultRecord]]]]]:
    query = select(ExecutionLedgerSet).order_by(ExecutionLedgerSet.created_at.desc(), ExecutionLedgerSet.id.desc())
    if scope_type:
        query = query.where(ExecutionLedgerSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(ExecutionLedgerSet.scope_ref == scope_ref)
    sets = list(session.scalars(query))
    return [get_execution_ledger_set(session, item.execution_ledger_set_id) for item in sets]
