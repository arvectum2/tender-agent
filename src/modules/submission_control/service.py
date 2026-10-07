from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.bid_packages.service import get_bid_package_set
from src.modules.event_log.service import append_event_record
from src.modules.submission_control.models import SubmissionAttempt, SubmissionExecutionRecord, SubmissionExecutionSet
from src.modules.submission_control.schemas import (
    BuildSubmissionControlRequest,
    RegisterSubmissionAttemptRequest,
    StartSubmissionExecutionRequest,
)
from src.modules.submission_readiness.service import get_submission_readiness_set
from src.shared.db.base import utcnow
from src.shared.enums import EventSeverity, ReadinessRecommendation, SubmissionAttemptStatus, SubmissionExecutionStatus
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import (
    next_submission_attempt_id,
    next_submission_execution_id,
    next_submission_execution_set_id,
)
from src.shared.validation import require_non_empty, require_same_reference


def _get_set(session: Session, submission_execution_set_id: str) -> SubmissionExecutionSet:
    record = session.scalar(
        select(SubmissionExecutionSet).where(
            SubmissionExecutionSet.submission_execution_set_id == submission_execution_set_id
        )
    )
    if not record:
        raise NotFoundError(f"Submission execution set '{submission_execution_set_id}' was not found")
    return record


def _get_record(session: Session, submission_execution_id: str) -> SubmissionExecutionRecord:
    record = session.scalar(
        select(SubmissionExecutionRecord).where(SubmissionExecutionRecord.submission_execution_id == submission_execution_id)
    )
    if not record:
        raise NotFoundError(f"Submission execution record '{submission_execution_id}' was not found")
    return record


def _get_records(session: Session, submission_execution_set_id: str) -> list[SubmissionExecutionRecord]:
    return list(
        session.scalars(
            select(SubmissionExecutionRecord)
            .where(SubmissionExecutionRecord.submission_execution_set_id == submission_execution_set_id)
            .order_by(SubmissionExecutionRecord.started_at.asc(), SubmissionExecutionRecord.id.asc())
        )
    )


def _get_attempts(session: Session, submission_execution_id: str) -> list[SubmissionAttempt]:
    return list(
        session.scalars(
            select(SubmissionAttempt)
            .where(SubmissionAttempt.submission_execution_id == submission_execution_id)
            .order_by(SubmissionAttempt.attempt_no.asc(), SubmissionAttempt.created_at.asc(), SubmissionAttempt.id.asc())
        )
    )


def build_submission_control(session: Session, payload: BuildSubmissionControlRequest) -> SubmissionExecutionSet:
    readiness_set, readiness_records = get_submission_readiness_set(session, payload.submission_readiness_set_id)
    bid_package_set, bid_package_records = get_bid_package_set(session, payload.bid_package_set_id)
    require_same_reference(payload.deal_id, readiness_set.deal_id, "deal_id")
    require_same_reference(payload.deal_id, bid_package_set.deal_id, "deal_id")
    if not readiness_records or not bid_package_records:
        raise ValidationError("Submission control requires persisted readiness and bid package records")

    latest_readiness_record = readiness_records[-1][0]
    if str(latest_readiness_record.recommendation) == str(ReadinessRecommendation.NOT_READY):
        raise ValidationError("Submission control cannot be built from a NOT_READY readiness recommendation")

    execution_set = SubmissionExecutionSet(
        submission_execution_set_id=next_submission_execution_set_id(
            session, SubmissionExecutionSet.submission_execution_set_id
        ),
        deal_id=payload.deal_id,
        submission_readiness_set_id=readiness_set.submission_readiness_set_id,
        bid_package_set_id=bid_package_set.bid_package_set_id,
        execution_status=SubmissionExecutionStatus.READY,
    )
    session.add(execution_set)
    session.flush()
    try:
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="submission_control_built",
            source_module_id="M-033",
            severity=EventSeverity.INFO,
            payload_json={
                "submission_execution_set_id": execution_set.submission_execution_set_id,
                "submission_readiness_set_id": readiness_set.submission_readiness_set_id,
                "bid_package_set_id": bid_package_set.bid_package_set_id,
            },
        )
        session.commit()
    except Exception as exc:
        execution_set.execution_status = SubmissionExecutionStatus.FAILED
        execution_set.updated_at = utcnow()
        session.add(execution_set)
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="submission_execution_failed",
            source_module_id="M-033",
            severity=EventSeverity.HIGH,
            payload_json={"submission_execution_set_id": execution_set.submission_execution_set_id, "error": str(exc)},
        )
        session.commit()
        raise
    session.refresh(execution_set)
    return execution_set


def start_submission_execution(session: Session, payload: StartSubmissionExecutionRequest) -> SubmissionExecutionRecord:
    execution_set = _get_set(session, payload.submission_execution_set_id)
    if str(execution_set.execution_status) == str(SubmissionExecutionStatus.SUBMITTED):
        raise ValidationError("Submission execution is already marked as SUBMITTED")

    record = SubmissionExecutionRecord(
        submission_execution_id=next_submission_execution_id(session, SubmissionExecutionRecord.submission_execution_id),
        submission_execution_set_id=execution_set.submission_execution_set_id,
        channel_type=payload.channel_type,
        initiated_by_ref=require_non_empty(payload.initiated_by_ref, "initiated_by_ref") if payload.initiated_by_ref else None,
        started_at=payload.started_at or utcnow(),
    )
    session.add(record)
    execution_set.execution_status = SubmissionExecutionStatus.IN_PROGRESS
    execution_set.updated_at = utcnow()
    session.add(execution_set)
    append_event_record(
        session,
        deal_id=execution_set.deal_id,
        event_code="submission_execution_started",
        source_module_id="M-033",
        severity=EventSeverity.INFO,
        payload_json={
            "submission_execution_set_id": execution_set.submission_execution_set_id,
            "submission_execution_id": record.submission_execution_id,
            "channel_type": str(payload.channel_type),
        },
    )
    session.commit()
    session.refresh(record)
    return record


def record_submission_attempt(session: Session, payload: RegisterSubmissionAttemptRequest) -> SubmissionAttempt:
    execution_record = _get_record(session, payload.submission_execution_id)
    execution_set = _get_set(session, execution_record.submission_execution_set_id)
    existing = session.scalar(
        select(SubmissionAttempt).where(
            SubmissionAttempt.submission_execution_id == execution_record.submission_execution_id,
            SubmissionAttempt.attempt_no == payload.attempt_no,
        )
    )
    if existing:
        raise ValidationError(
            f"Attempt number {payload.attempt_no} already exists for submission execution '{execution_record.submission_execution_id}'"
        )

    attempt = SubmissionAttempt(
        submission_attempt_id=next_submission_attempt_id(session, SubmissionAttempt.submission_attempt_id),
        submission_execution_id=execution_record.submission_execution_id,
        attempt_no=payload.attempt_no,
        attempt_status=payload.attempt_status,
        notes=require_non_empty(payload.notes, "notes") if payload.notes else None,
    )
    session.add(attempt)

    terminal_event_code: str | None = None
    terminal_status: SubmissionExecutionStatus | None = None
    if str(payload.attempt_status) == str(SubmissionAttemptStatus.STARTED):
        execution_set.execution_status = SubmissionExecutionStatus.IN_PROGRESS
    elif str(payload.attempt_status) == str(SubmissionAttemptStatus.SUCCEEDED):
        execution_set.execution_status = SubmissionExecutionStatus.SUBMITTED
        execution_record.finished_at = utcnow()
        terminal_event_code = "submission_execution_submitted"
        terminal_status = SubmissionExecutionStatus.SUBMITTED
    elif str(payload.attempt_status) == str(SubmissionAttemptStatus.FAILED):
        execution_set.execution_status = SubmissionExecutionStatus.FAILED
        execution_record.finished_at = utcnow()
        terminal_event_code = "submission_execution_failed"
        terminal_status = SubmissionExecutionStatus.FAILED
    else:
        execution_set.execution_status = SubmissionExecutionStatus.CANCELLED
        execution_record.finished_at = utcnow()
        terminal_event_code = "submission_execution_failed"
        terminal_status = SubmissionExecutionStatus.CANCELLED

    execution_record.updated_at = utcnow()
    execution_set.updated_at = utcnow()
    session.add(execution_record)
    session.add(execution_set)
    append_event_record(
        session,
        deal_id=execution_set.deal_id,
        event_code="submission_attempt_recorded",
        source_module_id="M-033",
        severity=EventSeverity.INFO,
        payload_json={
            "submission_execution_set_id": execution_set.submission_execution_set_id,
            "submission_execution_id": execution_record.submission_execution_id,
            "submission_attempt_id": attempt.submission_attempt_id,
            "attempt_no": attempt.attempt_no,
            "attempt_status": str(attempt.attempt_status),
        },
    )
    if terminal_event_code and terminal_status:
        append_event_record(
            session,
            deal_id=execution_set.deal_id,
            event_code=terminal_event_code,
            source_module_id="M-033",
            severity=EventSeverity.INFO if terminal_status == SubmissionExecutionStatus.SUBMITTED else EventSeverity.HIGH,
            payload_json={
                "submission_execution_set_id": execution_set.submission_execution_set_id,
                "submission_execution_id": execution_record.submission_execution_id,
                "submission_attempt_id": attempt.submission_attempt_id,
                "terminal_status": str(terminal_status),
            },
        )
    session.commit()
    if terminal_status == SubmissionExecutionStatus.SUBMITTED:
        try:
            from src.modules.daily_tender_run.post_go import advance_post_decision_for_deal

            advance_post_decision_for_deal(session, execution_set.deal_id)
        except Exception:  # noqa: BLE001 - submission evidence is already canonical
            session.rollback()
    session.refresh(attempt)
    return attempt


def get_submission_execution_set(
    session: Session,
    submission_execution_set_id: str,
) -> tuple[SubmissionExecutionSet, list[tuple[SubmissionExecutionRecord, list[SubmissionAttempt]]]]:
    execution_set = _get_set(session, submission_execution_set_id)
    records = _get_records(session, submission_execution_set_id)
    return execution_set, [(record, _get_attempts(session, record.submission_execution_id)) for record in records]


def list_submission_execution_sets(
    session: Session,
    *,
    deal_id: str | None = None,
) -> list[tuple[SubmissionExecutionSet, list[tuple[SubmissionExecutionRecord, list[SubmissionAttempt]]]]]:
    query = select(SubmissionExecutionSet).order_by(SubmissionExecutionSet.created_at.desc())
    if deal_id:
        query = query.where(SubmissionExecutionSet.deal_id == deal_id)
    sets = list(session.scalars(query))
    return [get_submission_execution_set(session, item.submission_execution_set_id) for item in sets]


def get_submission_execution_record(
    session: Session,
    submission_execution_id: str,
) -> tuple[SubmissionExecutionRecord, list[SubmissionAttempt]]:
    record = _get_record(session, submission_execution_id)
    return record, _get_attempts(session, submission_execution_id)
