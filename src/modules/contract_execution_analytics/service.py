from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.modules.claim_triggers.models import (
    ClaimTriggerFlag,
    ClaimTriggerLink,
    ClaimTriggerRecord,
    ClaimTriggerSet,
)
from src.modules.contract_execution_analytics.schemas import (
    ContractExecutionAnalyticsResponse,
    ExecutionEvidenceResponse,
    ExecutionStageResponse,
    LifecycleFactResponse,
    PaymentAnalyticsResponse,
    PenaltyClaimAnalyticsResponse,
    RiskSignalResponse,
    TimingAnalyticsResponse,
)
from src.modules.deal_closure.models import DealClosureRecord, DealClosureSet
from src.modules.deal_closure_reports.models import (
    DealClosureReportLink,
    DealClosureReportRecord,
    DealClosureReportSet,
)
from src.modules.deal_registry.models import Deal, DealExternalRef
from src.modules.execution_command.models import (
    ExecutionCommandBinding,
    ExecutionCommandRecord,
    ExecutionCommandSet,
)
from src.modules.incident_register.models import (
    IncidentRegisterEvent,
    IncidentRegisterFlag,
    IncidentRegisterRecord,
    IncidentRegisterSet,
)
from src.modules.outcome_intake.models import (
    OutcomeIntakeBinding,
    OutcomeIntakeRecord,
    OutcomeIntakeSet,
)
from src.modules.payment_collection.models import (
    PaymentCollectionEvent,
    PaymentCollectionRecord,
    PaymentCollectionSet,
)
from src.modules.payment_tracking.models import (
    PaymentTrackingEvent,
    PaymentTrackingRecord,
    PaymentTrackingSet,
)
from src.modules.postmortems.models import (
    PostmortemFinding,
    PostmortemRecord,
    PostmortemSet,
)
from src.modules.supplier_contracts.models import (
    SupplierContractRecord,
    SupplierContractSet,
)
from src.shared.errors import NotFoundError
from src.shared.execution_entry_package import load_execution_entry_context
from src.tender_research.models import ProcurementTender


def _ev(
    source_type: str,
    source_ref: str,
    *,
    field: str | None = None,
    value: object | None = None,
    source_url: str | None = None,
    observed_at=None,
) -> ExecutionEvidenceResponse:
    return ExecutionEvidenceResponse(
        source_type=source_type,
        source_ref=source_ref,
        field=field,
        value=str(value) if value is not None else None,
        source_url=source_url,
        observed_at=observed_at,
    )


def _unknown(summary: str) -> LifecycleFactResponse:
    return LifecycleFactResponse(state="UNKNOWN", summary=summary)


def _latest_by_deal(session: Session, model: type, deal_id: str):
    return session.scalar(
        select(model)
        .where(model.deal_id == deal_id)
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(1)
    )


def _latest_child(session: Session, model: type, field: str, value: str):
    return session.scalar(
        select(model)
        .where(getattr(model, field) == value)
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(1)
    )


def _ordered_children(session: Session, model: type, field: str, value: str) -> list:
    return list(
        session.scalars(
            select(model)
            .where(getattr(model, field) == value)
            .order_by(model.created_at.asc(), model.id.asc())
        )
    )


def _procurement_tender(
    session: Session, procurement_number: str | None
) -> ProcurementTender | None:
    if not procurement_number:
        return None
    return session.scalar(
        select(ProcurementTender)
        .where(
            or_(
                ProcurementTender.registry_number == procurement_number,
                ProcurementTender.purchase_number == procurement_number,
                ProcurementTender.external_id == procurement_number,
            )
        )
        .order_by(ProcurementTender.last_seen_at.desc(), ProcurementTender.id.desc())
        .limit(1)
    )


def _deal_external_refs(session: Session, deal_id: str) -> list[DealExternalRef]:
    return list(
        session.scalars(
            select(DealExternalRef)
            .where(DealExternalRef.deal_id == deal_id)
            .order_by(DealExternalRef.created_at.asc(), DealExternalRef.id.asc())
        )
    )


def _procurement_fact(
    session: Session,
    deal: Deal,
) -> LifecycleFactResponse:
    tender = _procurement_tender(session, deal.procurement_number)
    evidence = [
        _ev(
            "DEAL",
            f"DEAL:{deal.deal_id}",
            field="procurement_number",
            value=deal.procurement_number,
            observed_at=deal.updated_at,
        )
    ]
    for ref in _deal_external_refs(session, deal.deal_id):
        evidence.append(
            _ev(
                "DEAL_EXTERNAL_REF",
                f"{ref.ref_type}:{ref.ref_value}",
                field=ref.ref_type,
                value=ref.ref_value,
                observed_at=ref.created_at,
            )
        )
    if tender:
        source_ref = tender.registry_number or tender.external_id
        source_url = tender.eis_url or tender.platform_url
        evidence.extend(
            [
                _ev(
                    "PROCUREMENT_TENDER",
                    f"{tender.source}:{source_ref}",
                    field="title",
                    value=tender.title,
                    source_url=source_url,
                    observed_at=tender.last_seen_at,
                ),
                _ev(
                    "PROCUREMENT_TENDER",
                    f"{tender.source}:{source_ref}",
                    field="status",
                    value=tender.status,
                    source_url=source_url,
                    observed_at=tender.last_seen_at,
                ),
            ]
        )
        if tender.nmck_amount is not None:
            evidence.append(
                _ev(
                    "PROCUREMENT_TENDER",
                    f"{tender.source}:{source_ref}",
                    field="nmck_amount",
                    value=f"{tender.nmck_amount} {tender.currency or ''}".strip(),
                    source_url=source_url,
                    observed_at=tender.last_seen_at,
                )
            )
        return LifecycleFactResponse(
            state="OBSERVED",
            value_text=tender.registry_number
            or tender.purchase_number
            or tender.external_id,
            observed_at=tender.last_seen_at,
            summary="Exact procurement-number match found in the canonical procurement corpus.",
            evidence=evidence,
        )
    if deal.procurement_number:
        return LifecycleFactResponse(
            state="OBSERVED",
            value_text=deal.procurement_number,
            observed_at=deal.updated_at,
            summary=(
                "Procurement identity is registered on the canonical deal, but no exact-number "
                "ProcurementTender row is currently available; no name-based fallback is used."
            ),
            evidence=evidence,
        )
    return LifecycleFactResponse(
        state="UNKNOWN",
        summary="The canonical deal has no procurement number; procurement identity is not inferred by title/customer name.",
        evidence=evidence,
    )


def _execution_fact(
    session: Session,
    deal_id: str,
) -> tuple[
    LifecycleFactResponse, ExecutionCommandSet | None, ExecutionCommandRecord | None
]:
    execution_set = _latest_by_deal(session, ExecutionCommandSet, deal_id)
    if not execution_set:
        return (
            _unknown("No canonical execution-command set exists for this deal."),
            None,
            None,
        )
    record = _latest_child(
        session,
        ExecutionCommandRecord,
        "execution_command_set_id",
        execution_set.execution_command_set_id,
    )
    evidence = [
        _ev(
            "EXECUTION_COMMAND_SET",
            f"EXECUTION_COMMAND_SET:{execution_set.execution_command_set_id}",
            field="execution_status",
            value=execution_set.execution_status,
            observed_at=execution_set.updated_at,
        )
    ]
    for binding in _ordered_children(
        session,
        ExecutionCommandBinding,
        "execution_command_set_id",
        execution_set.execution_command_set_id,
    ):
        evidence.append(
            _ev(
                "EXECUTION_COMMAND_BINDING",
                f"{binding.source_object_type}:{binding.source_object_ref}",
                observed_at=binding.created_at,
            )
        )
    if record:
        evidence.append(
            _ev(
                "EXECUTION_COMMAND",
                f"EXECUTION_COMMAND:{record.execution_command_id}",
                field="current_phase",
                value=record.current_phase,
                observed_at=record.updated_at,
            )
        )
    return (
        LifecycleFactResponse(
            state="OBSERVED",
            value_text=str(execution_set.execution_status),
            observed_at=record.updated_at if record else execution_set.updated_at,
            summary=(
                f"Canonical execution status={execution_set.execution_status}"
                + (f", phase={record.current_phase}." if record else ".")
            ),
            evidence=evidence,
        ),
        execution_set,
        record,
    )


def _supplier_contract_fact(session: Session, deal_id: str) -> LifecycleFactResponse:
    contract_set = _latest_by_deal(session, SupplierContractSet, deal_id)
    if not contract_set:
        return _unknown("No canonical supplier contract exists for this deal.")
    record = _latest_child(
        session,
        SupplierContractRecord,
        "supplier_contract_set_id",
        contract_set.supplier_contract_set_id,
    )
    evidence = [
        _ev(
            "SUPPLIER_CONTRACT_SET",
            f"SUPPLIER_CONTRACT_SET:{contract_set.supplier_contract_set_id}",
            field="contract_status",
            value=contract_set.contract_status,
            observed_at=contract_set.updated_at,
        ),
        _ev(
            "SUPPLIER_PROFILE",
            f"SUPPLIER:{contract_set.supplier_id}",
            field="supplier_id",
            value=contract_set.supplier_id,
            observed_at=contract_set.created_at,
        ),
    ]
    if record:
        evidence.append(
            _ev(
                "SUPPLIER_CONTRACT",
                f"SUPPLIER_CONTRACT:{record.supplier_contract_id}",
                field="summary_text",
                value=record.summary_text,
                observed_at=record.updated_at,
            )
        )
    return LifecycleFactResponse(
        state="OBSERVED",
        value_text=str(contract_set.contract_status),
        observed_at=record.updated_at if record else contract_set.updated_at,
        summary=f"Latest canonical supplier contract status={contract_set.contract_status}.",
        evidence=evidence,
    )


def _execution_stages(
    session: Session,
    deal_id: str,
    execution_record: ExecutionCommandRecord | None,
) -> list[ExecutionStageResponse]:
    context = load_execution_entry_context(session, deal_id=deal_id)
    result: list[ExecutionStageResponse] = []
    if execution_record:
        result.append(
            ExecutionStageResponse(
                stage_code="EXECUTION_PHASE",
                stage_name="Current execution phase",
                state="OBSERVED",
                status=str(execution_record.current_phase),
                observed_at=execution_record.updated_at,
                evidence=[
                    _ev(
                        "EXECUTION_COMMAND",
                        f"EXECUTION_COMMAND:{execution_record.execution_command_id}",
                        field="current_phase",
                        value=execution_record.current_phase,
                        observed_at=execution_record.updated_at,
                    )
                ],
            )
        )
    for milestone, events in context.delivery_milestones:
        evidence = [
            _ev(
                "DELIVERY_MILESTONE",
                f"DELIVERY_MILESTONE:{milestone.delivery_milestone_id}",
                field="milestone_state",
                value=milestone.milestone_state,
                observed_at=milestone.updated_at,
            )
        ]
        for event in events:
            evidence.append(
                _ev(
                    "DELIVERY_MILESTONE_EVENT",
                    event.source_ref
                    or f"DELIVERY_MILESTONE_EVENT:{event.delivery_milestone_event_id}",
                    field="summary",
                    value=event.summary,
                    observed_at=event.event_timestamp,
                )
            )
        result.append(
            ExecutionStageResponse(
                stage_code=milestone.milestone_code,
                stage_name=milestone.milestone_name,
                state="OBSERVED",
                status=str(milestone.milestone_state),
                due_at=milestone.due_date,
                observed_at=events[-1].event_timestamp
                if events
                else milestone.updated_at,
                evidence=evidence,
            )
        )
    return result


def _payment_analytics(session: Session, deal_id: str) -> PaymentAnalyticsResponse:
    collection_set = _latest_by_deal(session, PaymentCollectionSet, deal_id)
    collection_record = None
    collection_events: list[PaymentCollectionEvent] = []
    if collection_set:
        collection_record = _latest_child(
            session,
            PaymentCollectionRecord,
            "payment_collection_set_id",
            collection_set.payment_collection_set_id,
        )
        if collection_record:
            collection_events = _ordered_children(
                session,
                PaymentCollectionEvent,
                "payment_collection_id",
                collection_record.payment_collection_id,
            )

    tracking_set = _latest_by_deal(session, PaymentTrackingSet, deal_id)
    tracking_record = None
    tracking_events: list[PaymentTrackingEvent] = []
    if tracking_set:
        tracking_record = _latest_child(
            session,
            PaymentTrackingRecord,
            "payment_tracking_set_id",
            tracking_set.payment_tracking_set_id,
        )
        if tracking_record:
            tracking_events = _ordered_children(
                session,
                PaymentTrackingEvent,
                "payment_tracking_id",
                tracking_record.payment_tracking_id,
            )

    if not collection_record and not tracking_record:
        return PaymentAnalyticsResponse(
            state="UNKNOWN",
            summary="No canonical payment collection/tracking record is available.",
        )

    evidence: list[ExecutionEvidenceResponse] = []
    if collection_set:
        evidence.append(
            _ev(
                "PAYMENT_COLLECTION_SET",
                f"PAYMENT_COLLECTION_SET:{collection_set.payment_collection_set_id}",
                field="collection_status",
                value=collection_set.collection_status,
                observed_at=collection_set.updated_at,
            )
        )
    if collection_record:
        evidence.extend(
            [
                _ev(
                    "PAYMENT_COLLECTION",
                    f"PAYMENT_COLLECTION:{collection_record.payment_collection_id}",
                    field="expected_amount",
                    value=collection_record.expected_amount,
                    observed_at=collection_record.updated_at,
                ),
                _ev(
                    "PAYMENT_COLLECTION",
                    f"PAYMENT_COLLECTION:{collection_record.payment_collection_id}",
                    field="collected_amount",
                    value=collection_record.collected_amount,
                    observed_at=collection_record.updated_at,
                ),
            ]
        )
        for event in collection_events:
            evidence.append(
                _ev(
                    "PAYMENT_COLLECTION_EVENT",
                    event.source_ref
                    or f"PAYMENT_COLLECTION_EVENT:{event.payment_collection_event_id}",
                    field="summary",
                    value=event.summary,
                    observed_at=event.event_timestamp,
                )
            )
    if tracking_set:
        evidence.append(
            _ev(
                "PAYMENT_TRACKING_SET",
                f"PAYMENT_TRACKING_SET:{tracking_set.payment_tracking_set_id}",
                field="payment_status",
                value=tracking_set.payment_status,
                observed_at=tracking_set.updated_at,
            )
        )
    if tracking_record:
        evidence.append(
            _ev(
                "PAYMENT_TRACKING",
                f"PAYMENT_TRACKING:{tracking_record.payment_tracking_id}",
                field="overdue_days",
                value=tracking_record.overdue_days,
                observed_at=tracking_record.updated_at,
            )
        )
        for event in tracking_events:
            evidence.append(
                _ev(
                    "PAYMENT_TRACKING_EVENT",
                    event.source_ref
                    or f"PAYMENT_TRACKING_EVENT:{event.payment_tracking_event_id}",
                    field="summary",
                    value=event.summary,
                    observed_at=event.event_timestamp,
                )
            )

    expected = (
        float(tracking_record.expected_amount)
        if tracking_record
        else float(collection_record.expected_amount)
        if collection_record
        else None
    )
    collected = (
        float(collection_record.collected_amount)
        if collection_record
        else float(tracking_record.paid_amount)
        if tracking_record
        else None
    )
    status = (
        str(tracking_set.payment_status)
        if tracking_set
        else str(collection_record.collection_state)
        if collection_record
        else None
    )
    return PaymentAnalyticsResponse(
        state="OBSERVED",
        status=status,
        expected_amount=expected,
        collected_amount=collected,
        currency_code=collection_record.currency_code if collection_record else None,
        overdue_days=int(tracking_record.overdue_days) if tracking_record else None,
        summary=(
            "Payment facts are projected from canonical collection/tracking records; "
            "collected amount is cash-receipt evidence, not final contract price."
        ),
        evidence=evidence,
    )


def _claim_penalty_analytics(
    session: Session, deal_id: str
) -> PenaltyClaimAnalyticsResponse:
    claim_set = _latest_by_deal(session, ClaimTriggerSet, deal_id)
    claim_record = None
    claim_flags: list[ClaimTriggerFlag] = []
    claim_links: list[ClaimTriggerLink] = []
    if claim_set:
        claim_record = _latest_child(
            session,
            ClaimTriggerRecord,
            "claim_trigger_set_id",
            claim_set.claim_trigger_set_id,
        )
        if claim_record:
            claim_flags = _ordered_children(
                session,
                ClaimTriggerFlag,
                "claim_trigger_id",
                claim_record.claim_trigger_id,
            )
            claim_links = _ordered_children(
                session,
                ClaimTriggerLink,
                "claim_trigger_id",
                claim_record.claim_trigger_id,
            )

    incident_set = _latest_by_deal(session, IncidentRegisterSet, deal_id)
    incident_records: list[IncidentRegisterRecord] = []
    if incident_set:
        incident_records = _ordered_children(
            session,
            IncidentRegisterRecord,
            "incident_register_set_id",
            incident_set.incident_register_set_id,
        )

    if not claim_set and not incident_set:
        return PenaltyClaimAnalyticsResponse(
            state="UNKNOWN",
            monetary_penalty_state="UNKNOWN",
            summary=(
                "No canonical claim-trigger or incident-register evidence is available. "
                "Missing records are not interpreted as absence of penalties or claims."
            ),
        )

    evidence: list[ExecutionEvidenceResponse] = []
    signals: list[RiskSignalResponse] = []
    if claim_set:
        evidence.append(
            _ev(
                "CLAIM_TRIGGER_SET",
                f"CLAIM_TRIGGER_SET:{claim_set.claim_trigger_set_id}",
                field="trigger_status",
                value=claim_set.trigger_status,
                observed_at=claim_set.updated_at,
            )
        )
    if claim_record:
        evidence.append(
            _ev(
                "CLAIM_TRIGGER",
                f"CLAIM_TRIGGER:{claim_record.claim_trigger_id}",
                field="trigger_reason",
                value=claim_record.trigger_reason,
                observed_at=claim_record.updated_at,
            )
        )
        link_refs = [link.source_ref for link in claim_links]
        for flag in claim_flags:
            signals.append(
                RiskSignalResponse(
                    signal_code=flag.flag_code,
                    severity=str(flag.severity),
                    summary=flag.summary,
                    evidence=[
                        _ev(
                            "CLAIM_TRIGGER_FLAG",
                            f"CLAIM_TRIGGER_FLAG:{flag.id}",
                            field="summary",
                            value=flag.summary,
                            observed_at=flag.created_at,
                        ),
                        *[
                            _ev(
                                "CLAIM_TRIGGER_LINK",
                                source_ref,
                                observed_at=link.created_at,
                            )
                            for source_ref, link in zip(
                                link_refs, claim_links, strict=False
                            )
                        ],
                    ],
                )
            )

    for record in incident_records:
        record_evidence = [
            _ev(
                "INCIDENT_REGISTER",
                f"INCIDENT_REGISTER:{record.incident_register_id}",
                field="summary_text",
                value=record.summary_text,
                observed_at=record.updated_at,
            )
        ]
        events = _ordered_children(
            session,
            IncidentRegisterEvent,
            "incident_register_id",
            record.incident_register_id,
        )
        for event in events:
            record_evidence.append(
                _ev(
                    "INCIDENT_REGISTER_EVENT",
                    event.source_ref
                    or f"INCIDENT_REGISTER_EVENT:{event.incident_register_event_id}",
                    field="summary",
                    value=event.summary,
                    observed_at=event.event_timestamp,
                )
            )
        flags = _ordered_children(
            session,
            IncidentRegisterFlag,
            "incident_register_id",
            record.incident_register_id,
        )
        if flags:
            for flag in flags:
                signals.append(
                    RiskSignalResponse(
                        signal_code=flag.flag_code,
                        severity=str(flag.severity),
                        summary=flag.summary,
                        evidence=record_evidence
                        + [
                            _ev(
                                "INCIDENT_REGISTER_FLAG",
                                f"INCIDENT_REGISTER_FLAG:{flag.id}",
                                field="summary",
                                value=flag.summary,
                                observed_at=flag.created_at,
                            )
                        ],
                    )
                )
        else:
            signals.append(
                RiskSignalResponse(
                    signal_code=str(record.incident_type),
                    severity=str(record.severity),
                    summary=record.summary_text,
                    evidence=record_evidence,
                )
            )

    return PenaltyClaimAnalyticsResponse(
        state="OBSERVED",
        claim_status=str(claim_set.trigger_status) if claim_set else None,
        monetary_penalty_state="UNKNOWN",
        monetary_penalty_amount=None,
        summary=(
            "Canonical claim/incident signals are shown as observed facts. "
            "No typed monetary penalty amount exists in these canonical stores, so no amount is inferred."
        ),
        signals=signals,
        evidence=evidence,
    )


def _outcome_fact(session: Session, deal_id: str) -> LifecycleFactResponse:
    outcome_set = _latest_by_deal(session, OutcomeIntakeSet, deal_id)
    if not outcome_set:
        return _unknown("No canonical outcome-intake set exists for this deal.")
    record = _latest_child(
        session,
        OutcomeIntakeRecord,
        "outcome_intake_set_id",
        outcome_set.outcome_intake_set_id,
    )
    if not record:
        return LifecycleFactResponse(
            state="UNKNOWN",
            summary="Outcome-intake set exists but has no persisted outcome record.",
            evidence=[
                _ev(
                    "OUTCOME_INTAKE_SET",
                    f"OUTCOME_INTAKE_SET:{outcome_set.outcome_intake_set_id}",
                    field="outcome_status",
                    value=outcome_set.outcome_status,
                    observed_at=outcome_set.updated_at,
                )
            ],
        )
    evidence = [
        _ev(
            "OUTCOME_INTAKE_SET",
            f"OUTCOME_INTAKE_SET:{outcome_set.outcome_intake_set_id}",
            field="outcome_status",
            value=outcome_set.outcome_status,
            observed_at=outcome_set.updated_at,
        ),
        _ev(
            "OUTCOME_INTAKE",
            f"OUTCOME_INTAKE:{record.outcome_intake_id}",
            field="outcome_code",
            value=record.outcome_code,
            observed_at=record.effective_at,
        ),
    ]
    for binding in _ordered_children(
        session,
        OutcomeIntakeBinding,
        "outcome_intake_id",
        record.outcome_intake_id,
    ):
        evidence.append(
            _ev(
                "DOCUMENT_ARTIFACT",
                binding.artifact_ref,
                field="binding_type",
                value=binding.binding_type,
                observed_at=binding.created_at,
            )
        )
    return LifecycleFactResponse(
        state="OBSERVED",
        value_text=str(record.outcome_code),
        observed_at=record.effective_at,
        summary=f"Canonical outcome={record.outcome_code}. {record.rationale}",
        evidence=evidence,
    )


def _closure_facts(
    session: Session,
    deal_id: str,
) -> tuple[LifecycleFactResponse, LifecycleFactResponse]:
    closure_set = _latest_by_deal(session, DealClosureSet, deal_id)
    if not closure_set:
        unknown = _unknown("No canonical deal-closure set exists for this deal.")
        return unknown, _unknown(
            "No canonical closure report exists because deal closure is unavailable."
        )
    record = _latest_child(
        session,
        DealClosureRecord,
        "deal_closure_set_id",
        closure_set.deal_closure_set_id,
    )
    closure_evidence = [
        _ev(
            "DEAL_CLOSURE_SET",
            f"DEAL_CLOSURE_SET:{closure_set.deal_closure_set_id}",
            field="closure_status",
            value=closure_set.closure_status,
            observed_at=closure_set.updated_at,
        )
    ]
    if record:
        closure_evidence.append(
            _ev(
                "DEAL_CLOSURE",
                f"DEAL_CLOSURE:{record.deal_closure_id}",
                field="closure_code",
                value=record.closure_code,
                observed_at=record.closed_at,
            )
        )
    closure = LifecycleFactResponse(
        state="OBSERVED",
        value_text=str(record.closure_code)
        if record
        else str(closure_set.closure_status),
        observed_at=record.closed_at if record else closure_set.updated_at,
        summary=record.summary_text
        if record
        else f"Closure status={closure_set.closure_status}.",
        evidence=closure_evidence,
    )

    report_set = _latest_by_deal(session, DealClosureReportSet, deal_id)
    if not report_set:
        return closure, _unknown("No canonical deal-closure report is available.")
    report = _latest_child(
        session,
        DealClosureReportRecord,
        "deal_closure_report_set_id",
        report_set.deal_closure_report_set_id,
    )
    if not report:
        return closure, LifecycleFactResponse(
            state="UNKNOWN",
            summary="Deal-closure report set exists but has no report record.",
            evidence=[
                _ev(
                    "DEAL_CLOSURE_REPORT_SET",
                    f"DEAL_CLOSURE_REPORT_SET:{report_set.deal_closure_report_set_id}",
                    field="report_status",
                    value=report_set.report_status,
                    observed_at=report_set.updated_at,
                )
            ],
        )
    evidence = [
        _ev(
            "DEAL_CLOSURE_REPORT_SET",
            f"DEAL_CLOSURE_REPORT_SET:{report_set.deal_closure_report_set_id}",
            field="report_status",
            value=report_set.report_status,
            observed_at=report_set.updated_at,
        ),
        _ev(
            "DEAL_CLOSURE_REPORT",
            f"DEAL_CLOSURE_REPORT:{report.deal_closure_report_id}",
            field="closure_health",
            value=report.closure_health,
            observed_at=report.updated_at,
        ),
    ]
    for link in _ordered_children(
        session,
        DealClosureReportLink,
        "deal_closure_report_id",
        report.deal_closure_report_id,
    ):
        evidence.append(
            _ev(
                "DEAL_CLOSURE_REPORT_LINK",
                link.source_ref,
                observed_at=link.created_at,
            )
        )
    return (
        closure,
        LifecycleFactResponse(
            state="OBSERVED",
            value_text=str(report.closure_health),
            observed_at=report.updated_at,
            summary=report.summary_text,
            evidence=evidence,
        ),
    )


def _postmortem_fact(session: Session, deal_id: str) -> LifecycleFactResponse:
    postmortem_set = _latest_by_deal(session, PostmortemSet, deal_id)
    if not postmortem_set:
        return _unknown("No canonical postmortem exists; no learning fact is inferred.")
    record = _latest_child(
        session,
        PostmortemRecord,
        "postmortem_set_id",
        postmortem_set.postmortem_set_id,
    )
    if not record:
        return LifecycleFactResponse(
            state="UNKNOWN",
            summary="Postmortem set exists but has no persisted record.",
            evidence=[
                _ev(
                    "POSTMORTEM_SET",
                    f"POSTMORTEM_SET:{postmortem_set.postmortem_set_id}",
                    field="postmortem_status",
                    value=postmortem_set.postmortem_status,
                    observed_at=postmortem_set.updated_at,
                )
            ],
        )
    evidence = [
        _ev(
            "POSTMORTEM_SET",
            f"POSTMORTEM_SET:{postmortem_set.postmortem_set_id}",
            field="postmortem_status",
            value=postmortem_set.postmortem_status,
            observed_at=postmortem_set.updated_at,
        ),
        _ev(
            "POSTMORTEM",
            f"POSTMORTEM:{record.postmortem_id}",
            field="summary_text",
            value=record.summary_text,
            observed_at=record.updated_at,
        ),
    ]
    for finding in _ordered_children(
        session,
        PostmortemFinding,
        "postmortem_id",
        record.postmortem_id,
    ):
        evidence.append(
            _ev(
                "POSTMORTEM_FINDING",
                f"POSTMORTEM_FINDING:{finding.id}",
                field="summary",
                value=finding.summary,
                observed_at=finding.created_at,
            )
        )
    return LifecycleFactResponse(
        state="OBSERVED",
        value_text=str(postmortem_set.postmortem_status),
        observed_at=record.updated_at,
        summary=record.summary_text,
        evidence=evidence,
    )


def _timing_analytics(
    execution_record: ExecutionCommandRecord | None,
    stages: list[ExecutionStageResponse],
    payment: PaymentAnalyticsResponse,
) -> TimingAnalyticsResponse:
    evidence: list[ExecutionEvidenceResponse] = []
    milestone_stages = [
        stage for stage in stages if stage.stage_code != "EXECUTION_PHASE"
    ]
    delayed = 0
    for stage in stages:
        evidence.extend(stage.evidence)
        if (
            stage.stage_code != "EXECUTION_PHASE"
            and stage.status
            and any(
                marker in stage.status.upper()
                for marker in ("DELAY", "OVERDUE", "LATE")
            )
        ):
            delayed += 1
    if execution_record:
        evidence.append(
            _ev(
                "EXECUTION_COMMAND",
                f"EXECUTION_COMMAND:{execution_record.execution_command_id}",
                field="current_phase",
                value=execution_record.current_phase,
                observed_at=execution_record.updated_at,
            )
        )
    if payment.state == "OBSERVED":
        evidence.extend(payment.evidence)
    if not execution_record and not stages and payment.overdue_days is None:
        return TimingAnalyticsResponse(
            state="UNKNOWN",
            summary="No canonical execution phase, milestone, or overdue-payment timing evidence is available.",
        )
    return TimingAnalyticsResponse(
        state="OBSERVED",
        current_phase=str(execution_record.current_phase) if execution_record else None,
        milestone_count=len(milestone_stages),
        delayed_milestone_count=delayed if milestone_stages else None,
        overdue_payment_days=payment.overdue_days,
        summary=(
            "Timing uses persisted execution phase, milestone states/due dates and explicit payment-overdue days. "
            "It does not infer lateness merely because a due date is in the past."
        ),
        evidence=evidence,
    )


def build_contract_execution_analytics(
    session: Session,
    deal_id: str,
) -> ContractExecutionAnalyticsResponse:
    deal = session.scalar(select(Deal).where(Deal.deal_id == deal_id))
    if not deal:
        raise NotFoundError(f"Deal '{deal_id}' was not found")

    procurement = _procurement_fact(session, deal)
    supplier_contract = _supplier_contract_fact(session, deal_id)
    execution, _execution_set, execution_record = _execution_fact(session, deal_id)
    stages = _execution_stages(session, deal_id, execution_record)
    payment = _payment_analytics(session, deal_id)
    timing = _timing_analytics(execution_record, stages, payment)
    penalties = _claim_penalty_analytics(session, deal_id)
    outcome = _outcome_fact(session, deal_id)
    closure, closure_health = _closure_facts(session, deal_id)
    postmortem = _postmortem_fact(session, deal_id)

    actual_price = LifecycleFactResponse(
        state="UNKNOWN",
        summary=(
            "No typed canonical final/actual contract-price field exists in the current lifecycle stores. "
            "Collected payment is exposed under payment analytics and is intentionally not relabeled as actual price."
        ),
        evidence=payment.evidence if payment.state == "OBSERVED" else [],
    )

    return ContractExecutionAnalyticsResponse(
        deal_id=deal.deal_id,
        procurement_number=deal.procurement_number,
        procurement=procurement,
        supplier_contract=supplier_contract,
        execution=execution,
        execution_stages=stages,
        payment=payment,
        timing=timing,
        penalties=penalties,
        actual_price=actual_price,
        outcome=outcome,
        closure=closure,
        postmortem=postmortem,
        closure_health=closure_health,
        learning_promotion_performed=False,
    )


def _numeric(value: float | None) -> float | None:
    return float(value) if value is not None else None


def contract_execution_dashboard_metrics(
    session: Session,
    deal_id: str,
) -> dict[str, str | float | None]:
    projection = build_contract_execution_analytics(session, deal_id)
    return {
        "lifecycle_contract_status": projection.supplier_contract.value_text,
        "lifecycle_execution_status": projection.execution.value_text,
        "lifecycle_execution_phase": projection.timing.current_phase,
        "lifecycle_payment_status": projection.payment.status,
        "lifecycle_collected_amount": _numeric(projection.payment.collected_amount),
        "lifecycle_overdue_days": _numeric(projection.payment.overdue_days),
        "lifecycle_claim_status": projection.penalties.claim_status,
        "lifecycle_outcome_code": projection.outcome.value_text,
        "lifecycle_closure_code": projection.closure.value_text,
        "lifecycle_closure_health": projection.closure_health.value_text,
        "lifecycle_actual_price_state": projection.actual_price.state,
        "lifecycle_learning_promotion": "disabled",
    }
