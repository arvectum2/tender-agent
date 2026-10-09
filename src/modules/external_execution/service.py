from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.event_log.service import append_event_record
from src.modules.execution_ledger.models import ExecutionLedgerRecord
from src.modules.external_execution.models import (
    ExternalExecutionRecord,
    ExternalExecutionResult,
    ExternalExecutionSet,
)
from src.modules.external_execution.schemas import (
    BuildExternalExecutionRequest,
    StartExternalExecutionRequest,
)
from src.modules.integration_tasks.models import (
    IntegrationTaskRecord,
    IntegrationTaskSet,
)
from src.modules.vendor_connectors.models import (
    VendorConnectorRecord,
    VendorConnectorSet,
)
from src.shared.control_package import (
    ensure_scope_exists,
    latest_execution_ledger_context,
    latest_integration_task_set,
    resolve_scope_deal_id,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    EventSeverity,
    ExecutionStatus,
    ExternalExecutionStatus,
    ExternalGatewayStatus,
    GatewayActionType,
    IntegrationTaskType,
    VendorStatus,
    WorkspaceScopeType,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_external_execution_id, next_external_execution_set_id


def _get_set(session: Session, external_execution_set_id: str) -> ExternalExecutionSet:
    record = session.scalar(
        select(ExternalExecutionSet).where(ExternalExecutionSet.external_execution_set_id == external_execution_set_id)
    )
    if not record:
        raise NotFoundError(f"External execution set '{external_execution_set_id}' was not found")
    return record


def _get_record(session: Session, external_execution_id: str) -> ExternalExecutionRecord:
    record = session.scalar(
        select(ExternalExecutionRecord).where(ExternalExecutionRecord.external_execution_id == external_execution_id)
    )
    if not record:
        raise NotFoundError(f"External execution record '{external_execution_id}' was not found")
    return record


def _get_records(session: Session, external_execution_set_id: str) -> list[ExternalExecutionRecord]:
    return list(
        session.scalars(
            select(ExternalExecutionRecord)
            .where(ExternalExecutionRecord.external_execution_set_id == external_execution_set_id)
            .order_by(ExternalExecutionRecord.created_at.asc(), ExternalExecutionRecord.id.asc())
        )
    )


def _get_results(session: Session, external_execution_id: str) -> list[ExternalExecutionResult]:
    return list(
        session.scalars(
            select(ExternalExecutionResult)
            .where(ExternalExecutionResult.external_execution_id == external_execution_id)
            .order_by(ExternalExecutionResult.created_at.asc(), ExternalExecutionResult.id.asc())
        )
    )


def _latest_vendor_connector_context(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[VendorConnectorSet | None, list[VendorConnectorRecord]]:
    vendor_set = session.scalar(
        select(VendorConnectorSet)
        .where(VendorConnectorSet.scope_type == scope_type, VendorConnectorSet.scope_ref == scope_ref)
        .order_by(VendorConnectorSet.created_at.desc(), VendorConnectorSet.id.desc())
        .limit(1)
    )
    if not vendor_set:
        return None, []
    records = list(
        session.scalars(
            select(VendorConnectorRecord)
            .where(VendorConnectorRecord.vendor_connector_set_id == vendor_set.vendor_connector_set_id)
            .order_by(VendorConnectorRecord.created_at.asc(), VendorConnectorRecord.id.asc())
        )
    )
    return vendor_set, records


def _latest_integration_task_set(
    session: Session,
    scope_type: str,
    scope_ref: str,
) -> tuple[IntegrationTaskSet | None, list[IntegrationTaskRecord]]:
    # Historical private name kept for call sites and monkeypatchable tests.
    return latest_integration_task_set(session, scope_type, scope_ref)

def _gateway_action_type(task_type: str) -> GatewayActionType:
    if task_type == IntegrationTaskType.EMAIL_SEND:
        return GatewayActionType.SEND
    if task_type in {IntegrationTaskType.SYNC_PULL, IntegrationTaskType.SYNC_PUSH}:
        return GatewayActionType.SYNC
    if task_type == IntegrationTaskType.EXPORT:
        return GatewayActionType.EXPORT
    if task_type == IntegrationTaskType.FOLLOW_UP:
        return GatewayActionType.FOLLOW_UP
    return GatewayActionType.OTHER


def build_external_execution(session: Session, payload: BuildExternalExecutionRequest) -> ExternalExecutionSet:
    if payload.scope_type in {WorkspaceScopeType.DEAL, WorkspaceScopeType.EXECUTION}:
        ensure_scope_exists(session, payload.scope_type, payload.scope_ref)
    gateway_set = ExternalExecutionSet(
        external_execution_set_id=next_external_execution_set_id(
            session, ExternalExecutionSet.external_execution_set_id
        ),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        gateway_status=ExternalGatewayStatus.BUILT,
    )
    session.add(gateway_set)
    session.flush()
    deal_id = resolve_scope_deal_id(session, payload.scope_type, payload.scope_ref)
    try:
        vendor_set, vendor_records = _latest_vendor_connector_context(session, payload.scope_type, payload.scope_ref)
        task_set, tasks = _latest_integration_task_set(session, payload.scope_type, payload.scope_ref)
        ledger_set, ledger_records = latest_execution_ledger_context(session, payload.scope_type, payload.scope_ref)
        if not vendor_set or not vendor_records:
            raise ValidationError("External execution requires persisted vendor connector profiles")
        if not task_set or not tasks:
            raise ValidationError("External execution requires persisted integration task context")
        if not ledger_set or not ledger_records:
            raise ValidationError("External execution requires persisted internal execution ledger context")

        vendor_by_connector = {record.connector_registry_id: record for record in vendor_records}
        task_by_id = {task.integration_task_id: task for task in tasks}

        candidate_count = 0
        for ledger_record, _results in ledger_records:
            task = task_by_id.get(ledger_record.integration_task_id)
            if not task:
                continue
            vendor = vendor_by_connector.get(task.connector_registry_id)
            if not vendor:
                continue
            candidate_count += 1
            session.add(
                ExternalExecutionRecord(
                    external_execution_id=next_external_execution_id(
                        session, ExternalExecutionRecord.external_execution_id
                    ),
                    external_execution_set_id=gateway_set.external_execution_set_id,
                    integration_task_id=task.integration_task_id,
                    execution_ledger_id=ledger_record.execution_ledger_id,
                    gateway_action_type=_gateway_action_type(task.task_type),
                    request_payload_json={
                        "scope_type": payload.scope_type,
                        "scope_ref": payload.scope_ref,
                        "connector_registry_id": task.connector_registry_id,
                        "vendor_connector_id": vendor.vendor_connector_id,
                        "vendor_code": vendor.vendor_code,
                        "task_type": task.task_type,
                        "task_payload_json": task.task_payload_json,
                    },
                    execution_status=ExternalExecutionStatus.STARTED,
                    started_at=None,
                    finished_at=None,
                )
            )
            session.flush()
        if candidate_count == 0:
            raise ValidationError("External execution requires gateway-ready integration task candidates")

        append_event_record(
            session,
            deal_id=deal_id,
            event_code="external_execution_built",
            source_module_id="M-062",
            severity=EventSeverity.INFO,
            payload_json={
                "external_execution_set_id": gateway_set.external_execution_set_id,
                "vendor_connector_set_id": vendor_set.vendor_connector_set_id,
                "integration_task_set_id": task_set.integration_task_set_id,
                "execution_ledger_set_id": ledger_set.execution_ledger_set_id,
                "candidate_count": candidate_count,
            },
        )
        session.commit()
        session.refresh(gateway_set)
        return gateway_set
    except Exception as exc:
        gateway_set.gateway_status = ExternalGatewayStatus.FAILED
        gateway_set.updated_at = utcnow()
        append_event_record(
            session,
            deal_id=deal_id,
            event_code="external_execution_failed",
            source_module_id="M-062",
            severity=EventSeverity.HIGH,
            payload_json={"external_execution_set_id": gateway_set.external_execution_set_id, "error": str(exc)},
        )
        session.commit()
        raise


def start_external_execution(session: Session, payload: StartExternalExecutionRequest) -> ExternalExecutionRecord:
    record = _get_record(session, payload.external_execution_id)
    gateway_set = _get_set(session, record.external_execution_set_id)
    deal_id = resolve_scope_deal_id(session, gateway_set.scope_type, gateway_set.scope_ref)
    integration_task = session.scalar(
        select(IntegrationTaskRecord).where(IntegrationTaskRecord.integration_task_id == record.integration_task_id)
    )
    execution_ledger = session.scalar(
        select(ExecutionLedgerRecord).where(ExecutionLedgerRecord.execution_ledger_id == record.execution_ledger_id)
    )
    if not integration_task or not execution_ledger:
        raise ValidationError("External execution requires persisted integration task and execution ledger context")
    if record.started_at is not None:
        raise ValidationError("External execution record is already started")
    if execution_ledger.execution_status != ExecutionStatus.SUCCEEDED:
        raise ValidationError("External execution start requires succeeded internal execution ledger context")

    vendor_connector_id = str(record.request_payload_json.get("vendor_connector_id"))
    vendor = session.scalar(
        select(VendorConnectorRecord).where(VendorConnectorRecord.vendor_connector_id == vendor_connector_id)
    )
    if not vendor:
        raise ValidationError("External execution requires persisted vendor connector context")

    record.started_at = utcnow()
    record.updated_at = utcnow()
    gateway_set.gateway_status = ExternalGatewayStatus.ACTIVE
    gateway_set.updated_at = utcnow()
    append_event_record(
        session,
        deal_id=deal_id,
        event_code="external_execution_started",
        source_module_id="M-062",
        severity=EventSeverity.INFO,
        payload_json={
            "external_execution_set_id": gateway_set.external_execution_set_id,
            "external_execution_id": record.external_execution_id,
            "integration_task_id": record.integration_task_id,
            "execution_ledger_id": record.execution_ledger_id,
        },
    )

    if vendor.vendor_status == VendorStatus.ACTIVE:
        record.execution_status = ExternalExecutionStatus.SUCCEEDED
        result = ExternalExecutionResult(
            external_execution_id=record.external_execution_id,
            result_code="GATEWAY_CALL_ACCEPTED",
            result_summary=f"External execution accepted by vendor gateway {vendor.vendor_code}.",
            response_payload_json={
                "vendor_connector_id": vendor.vendor_connector_id,
                "vendor_code": vendor.vendor_code,
                "connector_registry_id": integration_task.connector_registry_id,
                "gateway_action_type": record.gateway_action_type,
                "status": ExternalExecutionStatus.SUCCEEDED,
            },
            artifact_ref=None,
        )
        event_code = "external_execution_succeeded"
        severity = EventSeverity.INFO
    else:
        record.execution_status = ExternalExecutionStatus.FAILED
        gateway_set.gateway_status = ExternalGatewayStatus.FAILED
        result = ExternalExecutionResult(
            external_execution_id=record.external_execution_id,
            result_code="GATEWAY_UNAVAILABLE",
            result_summary=f"External execution failed because vendor gateway {vendor.vendor_code} is not ACTIVE.",
            response_payload_json={
                "vendor_connector_id": vendor.vendor_connector_id,
                "vendor_code": vendor.vendor_code,
                "connector_registry_id": integration_task.connector_registry_id,
                "gateway_action_type": record.gateway_action_type,
                "status": ExternalExecutionStatus.FAILED,
            },
            artifact_ref=None,
        )
        event_code = "external_execution_failed"
        severity = EventSeverity.HIGH

    record.finished_at = utcnow()
    session.add(result)
    session.flush()
    append_event_record(
        session,
        deal_id=deal_id,
        event_code=event_code,
        source_module_id="M-062",
        severity=severity,
        payload_json={
            "external_execution_set_id": gateway_set.external_execution_set_id,
            "external_execution_id": record.external_execution_id,
            "result_code": result.result_code,
        },
    )
    session.commit()
    session.refresh(record)
    return record


def get_external_execution_set(
    session: Session,
    external_execution_set_id: str,
) -> tuple[ExternalExecutionSet, list[tuple[ExternalExecutionRecord, list[ExternalExecutionResult]]]]:
    gateway_set = _get_set(session, external_execution_set_id)
    records = [(record, _get_results(session, record.external_execution_id)) for record in _get_records(session, external_execution_set_id)]
    return gateway_set, records


def get_external_execution_record(
    session: Session,
    external_execution_id: str,
) -> tuple[ExternalExecutionRecord, list[ExternalExecutionResult]]:
    record = _get_record(session, external_execution_id)
    return record, _get_results(session, external_execution_id)


def list_external_execution_sets(
    session: Session,
    *,
    scope_type: WorkspaceScopeType | None = None,
    scope_ref: str | None = None,
) -> list[tuple[ExternalExecutionSet, list[tuple[ExternalExecutionRecord, list[ExternalExecutionResult]]]]]:
    query = select(ExternalExecutionSet).order_by(
        ExternalExecutionSet.created_at.desc(),
        ExternalExecutionSet.id.desc(),
    )
    if scope_type:
        query = query.where(ExternalExecutionSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(ExternalExecutionSet.scope_ref == scope_ref)
    return [get_external_execution_set(session, item.external_execution_set_id) for item in session.scalars(query)]
