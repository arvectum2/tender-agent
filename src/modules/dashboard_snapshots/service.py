from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.contract_execution_analytics.service import (
    contract_execution_dashboard_metrics,
)
from src.modules.dashboard_snapshots.models import (
    DashboardMetricRecord,
    DashboardSnapshotRecord,
    DashboardSnapshotSet,
)
from src.modules.dashboard_snapshots.schemas import BuildDashboardSnapshotRequest
from src.modules.deal_closure.models import DealClosureSet
from src.modules.deal_registry.models import Deal
from src.modules.event_log.service import append_event_record
from src.modules.execution_command.models import (
    ExecutionCommandRecord,
    ExecutionCommandSet,
)
from src.modules.incidents.models import IncidentRecord, IncidentSet
from src.modules.kpi_learning.models import KPILearningRecord, KPILearningSet
from src.modules.outcome_intake.models import OutcomeIntakeRecord, OutcomeIntakeSet
from src.modules.payment_collection.models import (
    PaymentCollectionRecord,
    PaymentCollectionSet,
)
from src.modules.shipping_acceptance.models import (
    ShippingAcceptanceRecord,
    ShippingAcceptanceSet,
)
from src.shared.db.base import utcnow
from src.shared.enums import DashboardScopeType, DashboardSnapshotStatus, EventSeverity
from src.shared.errors import NotFoundError
from src.shared.ids import next_dashboard_snapshot_id, next_dashboard_snapshot_set_id


def _get_set(session: Session, dashboard_snapshot_set_id: str) -> DashboardSnapshotSet:
    record = session.scalar(
        select(DashboardSnapshotSet).where(DashboardSnapshotSet.dashboard_snapshot_set_id == dashboard_snapshot_set_id)
    )
    if not record:
        raise NotFoundError(f"Dashboard snapshot set '{dashboard_snapshot_set_id}' was not found")
    return record


def _get_record(session: Session, dashboard_snapshot_id: str) -> DashboardSnapshotRecord:
    record = session.scalar(
        select(DashboardSnapshotRecord).where(DashboardSnapshotRecord.dashboard_snapshot_id == dashboard_snapshot_id)
    )
    if not record:
        raise NotFoundError(f"Dashboard snapshot record '{dashboard_snapshot_id}' was not found")
    return record


def _get_records(session: Session, dashboard_snapshot_set_id: str) -> list[DashboardSnapshotRecord]:
    return list(
        session.scalars(
            select(DashboardSnapshotRecord)
            .where(DashboardSnapshotRecord.dashboard_snapshot_set_id == dashboard_snapshot_set_id)
            .order_by(DashboardSnapshotRecord.created_at.asc(), DashboardSnapshotRecord.id.asc())
        )
    )


def _get_metrics(session: Session, dashboard_snapshot_id: str) -> list[DashboardMetricRecord]:
    return list(
        session.scalars(
            select(DashboardMetricRecord)
            .where(DashboardMetricRecord.dashboard_snapshot_id == dashboard_snapshot_id)
            .order_by(DashboardMetricRecord.created_at.asc(), DashboardMetricRecord.id.asc())
        )
    )


def _metric(metric_code: str, numeric: float | int | None = None, text: str | None = None) -> dict:
    return {
        "metric_code": metric_code,
        "metric_value_numeric": float(numeric) if numeric is not None else None,
        "metric_value_text": text,
    }


def _deal_metrics(session: Session, deal_id: str) -> tuple[str, list[dict]]:
    deal = session.scalar(select(Deal).where(Deal.deal_id == deal_id))
    if not deal:
        raise NotFoundError(f"Deal '{deal_id}' was not found")
    latest_execution = session.scalar(
        select(ExecutionCommandSet)
        .where(ExecutionCommandSet.deal_id == deal_id)
        .order_by(ExecutionCommandSet.created_at.desc(), ExecutionCommandSet.id.desc())
        .limit(1)
    )
    latest_payment = session.scalar(
        select(PaymentCollectionSet)
        .where(PaymentCollectionSet.deal_id == deal_id)
        .order_by(PaymentCollectionSet.created_at.desc(), PaymentCollectionSet.id.desc())
        .limit(1)
    )
    latest_closure = session.scalar(
        select(DealClosureSet)
        .where(DealClosureSet.deal_id == deal_id)
        .order_by(DealClosureSet.created_at.desc(), DealClosureSet.id.desc())
        .limit(1)
    )
    latest_kpi_record = session.scalar(
        select(KPILearningRecord)
        .join(KPILearningSet, KPILearningSet.kpi_learning_set_id == KPILearningRecord.kpi_learning_set_id)
        .where(KPILearningSet.deal_id == deal_id)
        .order_by(KPILearningRecord.created_at.desc(), KPILearningRecord.id.desc())
        .limit(1)
    )
    latest_outcome = session.scalar(
        select(OutcomeIntakeRecord)
        .join(OutcomeIntakeSet, OutcomeIntakeSet.outcome_intake_set_id == OutcomeIntakeRecord.outcome_intake_set_id)
        .where(OutcomeIntakeSet.deal_id == deal_id)
        .order_by(OutcomeIntakeRecord.effective_at.desc(), OutcomeIntakeRecord.id.desc())
        .limit(1)
    )
    incident_count = int(
        session.scalar(
            select(func.count(IncidentRecord.id))
            .join(IncidentSet, IncidentSet.incident_set_id == IncidentRecord.incident_set_id)
            .where(IncidentSet.deal_id == deal_id)
        )
        or 0
    )
    metrics = [
        _metric("deal_status", text=str(deal.current_status)),
        _metric("incident_count", incident_count),
        _metric("execution_status", text=str(latest_execution.execution_status) if latest_execution else None),
        _metric("payment_status", text=str(latest_payment.collection_status) if latest_payment else None),
        _metric("closure_status", text=str(latest_closure.closure_status) if latest_closure else None),
        _metric("outcome_code", text=str(latest_outcome.outcome_code) if latest_outcome else None),
        _metric("margin_estimate", latest_kpi_record.margin_estimate if latest_kpi_record else None),
    ]
    lifecycle = contract_execution_dashboard_metrics(session, deal_id)
    metrics.extend(
        _metric(code, value if isinstance(value, (int, float)) else None, None if isinstance(value, (int, float)) else value)
        for code, value in lifecycle.items()
    )
    summary = f"Deal snapshot for {deal_id}: status={deal.current_status}, incidents={incident_count}."
    return summary, metrics


def _execution_metrics(session: Session, execution_command_set_id: str) -> tuple[str, list[dict]]:
    execution_set = session.scalar(
        select(ExecutionCommandSet).where(ExecutionCommandSet.execution_command_set_id == execution_command_set_id)
    )
    if not execution_set:
        raise NotFoundError(f"Execution command set '{execution_command_set_id}' was not found")
    latest_execution_record = session.scalar(
        select(ExecutionCommandRecord)
        .where(ExecutionCommandRecord.execution_command_set_id == execution_command_set_id)
        .order_by(ExecutionCommandRecord.created_at.desc(), ExecutionCommandRecord.id.desc())
        .limit(1)
    )
    incident_count = int(
        session.scalar(
            select(func.count(IncidentRecord.id))
            .join(IncidentSet, IncidentSet.incident_set_id == IncidentRecord.incident_set_id)
            .where(IncidentSet.execution_command_set_id == execution_command_set_id)
        )
        or 0
    )
    shipping_set = session.scalar(
        select(ShippingAcceptanceSet)
        .where(ShippingAcceptanceSet.deal_id == execution_set.deal_id)
        .order_by(ShippingAcceptanceSet.created_at.desc(), ShippingAcceptanceSet.id.desc())
        .limit(1)
    )
    shipping_record = None
    if shipping_set:
        shipping_record = session.scalar(
            select(ShippingAcceptanceRecord)
            .where(ShippingAcceptanceRecord.shipping_acceptance_set_id == shipping_set.shipping_acceptance_set_id)
            .order_by(ShippingAcceptanceRecord.created_at.desc(), ShippingAcceptanceRecord.id.desc())
            .limit(1)
        )
    payment_set = session.scalar(
        select(PaymentCollectionSet)
        .where(PaymentCollectionSet.execution_command_set_id == execution_command_set_id)
        .order_by(PaymentCollectionSet.created_at.desc(), PaymentCollectionSet.id.desc())
        .limit(1)
    )
    payment_record = None
    if payment_set:
        payment_record = session.scalar(
            select(PaymentCollectionRecord)
            .where(PaymentCollectionRecord.payment_collection_set_id == payment_set.payment_collection_set_id)
            .order_by(PaymentCollectionRecord.created_at.desc(), PaymentCollectionRecord.id.desc())
            .limit(1)
        )
    metrics = [
        _metric("execution_status", text=str(execution_set.execution_status)),
        _metric("execution_phase", text=str(latest_execution_record.current_phase) if latest_execution_record else None),
        _metric("incident_count", incident_count),
        _metric("shipping_state", text=str(shipping_record.current_state) if shipping_record else None),
        _metric("collection_state", text=str(payment_record.collection_state) if payment_record else None),
        _metric("collected_amount", payment_record.collected_amount if payment_record else None),
    ]
    summary = (
        f"Execution snapshot for {execution_command_set_id}: "
        f"status={execution_set.execution_status}, incidents={incident_count}."
    )
    return summary, metrics


def _pipeline_metrics(session: Session) -> tuple[str, list[dict]]:
    total_deals = int(session.scalar(select(func.count(Deal.id))) or 0)
    total_executions = int(session.scalar(select(func.count(ExecutionCommandSet.id))) or 0)
    closed_deals = int(session.scalar(select(func.count(DealClosureSet.id))) or 0)
    total_incidents = int(session.scalar(select(func.count(IncidentRecord.id))) or 0)
    metrics = [
        _metric("total_deals", total_deals),
        _metric("total_execution_sets", total_executions),
        _metric("closed_deal_sets", closed_deals),
        _metric("total_incidents", total_incidents),
    ]
    summary = f"Pipeline snapshot: deals={total_deals}, closures={closed_deals}, incidents={total_incidents}."
    return summary, metrics


def _global_metrics(session: Session) -> tuple[str, list[dict]]:
    total_deals = int(session.scalar(select(func.count(Deal.id))) or 0)
    total_kpi_sets = int(session.scalar(select(func.count(KPILearningSet.id))) or 0)
    total_dashboard_sets = int(session.scalar(select(func.count(DashboardSnapshotSet.id))) or 0)
    total_incidents = int(session.scalar(select(func.count(IncidentRecord.id))) or 0)
    metrics = [
        _metric("total_deals", total_deals),
        _metric("total_kpi_sets", total_kpi_sets),
        _metric("total_dashboard_sets", total_dashboard_sets),
        _metric("total_incidents", total_incidents),
    ]
    summary = f"Global snapshot: deals={total_deals}, kpi_sets={total_kpi_sets}, incidents={total_incidents}."
    return summary, metrics


def build_dashboard_snapshot(session: Session, payload: BuildDashboardSnapshotRequest) -> DashboardSnapshotSet:
    snapshot_set = DashboardSnapshotSet(
        dashboard_snapshot_set_id=next_dashboard_snapshot_set_id(session, DashboardSnapshotSet.dashboard_snapshot_set_id),
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        snapshot_status=DashboardSnapshotStatus.BUILT,
    )
    session.add(snapshot_set)
    session.flush()
    try:
        if payload.scope_type == DashboardScopeType.DEAL:
            summary, metrics = _deal_metrics(session, payload.scope_ref)
        elif payload.scope_type == DashboardScopeType.EXECUTION:
            summary, metrics = _execution_metrics(session, payload.scope_ref)
        elif payload.scope_type == DashboardScopeType.PIPELINE:
            summary, metrics = _pipeline_metrics(session)
        else:
            summary, metrics = _global_metrics(session)

        snapshot_record = DashboardSnapshotRecord(
            dashboard_snapshot_id=next_dashboard_snapshot_id(session, DashboardSnapshotRecord.dashboard_snapshot_id),
            dashboard_snapshot_set_id=snapshot_set.dashboard_snapshot_set_id,
            summary_text=summary,
        )
        session.add(snapshot_record)
        session.flush()
        for metric in metrics:
            session.add(DashboardMetricRecord(dashboard_snapshot_id=snapshot_record.dashboard_snapshot_id, **metric))
        snapshot_set.updated_at = utcnow()
        session.add(snapshot_set)
        append_event_record(
            session,
            deal_id=payload.scope_ref if payload.scope_type == DashboardScopeType.DEAL else None,
            event_code="dashboard_snapshot_built",
            source_module_id="M-048",
            severity=EventSeverity.INFO,
            payload_json={
                "dashboard_snapshot_set_id": snapshot_set.dashboard_snapshot_set_id,
                "dashboard_snapshot_id": snapshot_record.dashboard_snapshot_id,
                "scope_type": str(payload.scope_type),
                "scope_ref": payload.scope_ref,
                "metric_count": len(metrics),
            },
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        failed_set = DashboardSnapshotSet(
            dashboard_snapshot_set_id=snapshot_set.dashboard_snapshot_set_id,
            scope_type=payload.scope_type,
            scope_ref=payload.scope_ref,
            snapshot_status=DashboardSnapshotStatus.FAILED,
        )
        session.add(failed_set)
        append_event_record(
            session,
            deal_id=payload.scope_ref if payload.scope_type == DashboardScopeType.DEAL else None,
            event_code="dashboard_snapshot_failed",
            source_module_id="M-048",
            severity=EventSeverity.HIGH,
            payload_json={"dashboard_snapshot_set_id": snapshot_set.dashboard_snapshot_set_id, "error": str(exc)},
        )
        session.commit()
        raise
    session.refresh(snapshot_set)
    return snapshot_set


def get_dashboard_snapshot_set(
    session: Session,
    dashboard_snapshot_set_id: str,
) -> tuple[DashboardSnapshotSet, list[tuple[DashboardSnapshotRecord, list[DashboardMetricRecord]]]]:
    snapshot_set = _get_set(session, dashboard_snapshot_set_id)
    records = _get_records(session, dashboard_snapshot_set_id)
    return snapshot_set, [(record, _get_metrics(session, record.dashboard_snapshot_id)) for record in records]


def list_dashboard_snapshot_sets(
    session: Session,
    *,
    scope_type: DashboardScopeType | None = None,
    scope_ref: str | None = None,
) -> list[tuple[DashboardSnapshotSet, list[tuple[DashboardSnapshotRecord, list[DashboardMetricRecord]]]]]:
    query = select(DashboardSnapshotSet).order_by(DashboardSnapshotSet.created_at.desc())
    if scope_type:
        query = query.where(DashboardSnapshotSet.scope_type == scope_type)
    if scope_ref:
        query = query.where(DashboardSnapshotSet.scope_ref == scope_ref)
    sets = list(session.scalars(query))
    return [get_dashboard_snapshot_set(session, item.dashboard_snapshot_set_id) for item in sets]


def get_dashboard_snapshot_record(
    session: Session,
    dashboard_snapshot_id: str,
) -> tuple[DashboardSnapshotRecord, list[DashboardMetricRecord]]:
    record = _get_record(session, dashboard_snapshot_id)
    return record, _get_metrics(session, dashboard_snapshot_id)
