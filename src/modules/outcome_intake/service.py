from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.event_log.service import append_event_record
from src.modules.outcome_intake.models import (
    OutcomeIntakeBinding,
    OutcomeIntakeRecord,
    OutcomeIntakeSet,
)
from src.modules.outcome_intake.schemas import RegisterOutcomeIntakeRequest
from src.modules.post_submission.service import get_post_submission_tracker_set
from src.shared.db.base import utcnow
from src.shared.enums import EventSeverity, OutcomeStatus
from src.shared.errors import NotFoundError
from src.shared.ids import next_outcome_intake_id, next_outcome_intake_set_id
from src.shared.validation import require_non_empty, require_same_reference


def _get_set(session: Session, outcome_intake_set_id: str) -> OutcomeIntakeSet:
    record = session.scalar(select(OutcomeIntakeSet).where(OutcomeIntakeSet.outcome_intake_set_id == outcome_intake_set_id))
    if not record:
        raise NotFoundError(f"Outcome intake set '{outcome_intake_set_id}' was not found")
    return record


def _get_record(session: Session, outcome_intake_id: str) -> OutcomeIntakeRecord:
    record = session.scalar(select(OutcomeIntakeRecord).where(OutcomeIntakeRecord.outcome_intake_id == outcome_intake_id))
    if not record:
        raise NotFoundError(f"Outcome intake record '{outcome_intake_id}' was not found")
    return record


def _get_records(session: Session, outcome_intake_set_id: str) -> list[OutcomeIntakeRecord]:
    return list(
        session.scalars(
            select(OutcomeIntakeRecord)
            .where(OutcomeIntakeRecord.outcome_intake_set_id == outcome_intake_set_id)
            .order_by(OutcomeIntakeRecord.effective_at.asc(), OutcomeIntakeRecord.id.asc())
        )
    )


def _get_bindings(session: Session, outcome_intake_id: str) -> list[OutcomeIntakeBinding]:
    return list(
        session.scalars(
            select(OutcomeIntakeBinding)
            .where(OutcomeIntakeBinding.outcome_intake_id == outcome_intake_id)
            .order_by(OutcomeIntakeBinding.created_at.asc(), OutcomeIntakeBinding.id.asc())
        )
    )


def _has_prior_outcome(session: Session, *, deal_id: str, post_submission_tracker_set_id: str) -> bool:
    existing = session.scalar(
        select(OutcomeIntakeSet.id)
        .where(
            OutcomeIntakeSet.deal_id == deal_id,
            OutcomeIntakeSet.post_submission_tracker_set_id == post_submission_tracker_set_id,
        )
        .limit(1)
    )
    return existing is not None


def register_outcome_intake(session: Session, payload: RegisterOutcomeIntakeRequest) -> OutcomeIntakeSet:
    tracker_set, tracker_records = get_post_submission_tracker_set(session, payload.post_submission_tracker_set_id)
    require_same_reference(payload.deal_id, tracker_set.deal_id, "deal_id")
    has_prior_outcome = _has_prior_outcome(
        session,
        deal_id=payload.deal_id,
        post_submission_tracker_set_id=tracker_set.post_submission_tracker_set_id,
    )

    outcome_set = OutcomeIntakeSet(
        outcome_intake_set_id=next_outcome_intake_set_id(session, OutcomeIntakeSet.outcome_intake_set_id),
        deal_id=payload.deal_id,
        post_submission_tracker_set_id=tracker_set.post_submission_tracker_set_id,
        outcome_status=OutcomeStatus.REVISED if has_prior_outcome else OutcomeStatus.RECORDED,
    )
    session.add(outcome_set)
    session.flush()
    try:
        outcome_record = OutcomeIntakeRecord(
            outcome_intake_id=next_outcome_intake_id(session, OutcomeIntakeRecord.outcome_intake_id),
            outcome_intake_set_id=outcome_set.outcome_intake_set_id,
            outcome_code=payload.outcome_code,
            effective_at=payload.effective_at or utcnow(),
            rationale=require_non_empty(payload.rationale, "rationale"),
        )
        session.add(outcome_record)
        session.flush()
        for binding in payload.bindings:
            session.add(
                OutcomeIntakeBinding(
                    outcome_intake_id=outcome_record.outcome_intake_id,
                    artifact_ref=binding.artifact_ref,
                    binding_type=binding.binding_type,
                )
            )
        outcome_set.updated_at = utcnow()
        session.add(outcome_set)
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="outcome_intake_revised" if has_prior_outcome else "outcome_intake_recorded",
            source_module_id="M-037",
            severity=EventSeverity.INFO,
            payload_json={
                "outcome_intake_set_id": outcome_set.outcome_intake_set_id,
                "outcome_intake_id": outcome_record.outcome_intake_id,
                "post_submission_tracker_set_id": tracker_set.post_submission_tracker_set_id,
                "tracker_record_count": len(tracker_records),
            },
        )
        session.commit()
    except Exception as exc:
        outcome_set.outcome_status = OutcomeStatus.FAILED
        outcome_set.updated_at = utcnow()
        session.add(outcome_set)
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="outcome_intake_failed",
            source_module_id="M-037",
            severity=EventSeverity.HIGH,
            payload_json={"outcome_intake_set_id": outcome_set.outcome_intake_set_id, "error": str(exc)},
        )
        session.commit()
        raise

    try:
        from src.modules.daily_tender_run.post_go import advance_post_decision_for_deal

        advance_post_decision_for_deal(session, payload.deal_id)
    except Exception:  # noqa: BLE001 - outcome evidence is already canonical
        session.rollback()

    # Push is a non-authoritative notification side effect. It runs only after
    # the canonical outcome commit and cannot turn a recorded outcome into a
    # failed one.
    from src.modules.mobile_api.push import safely_dispatch_mobile_push_event

    safely_dispatch_mobile_push_event(
        session,
        event_type="OUTCOME_AVAILABLE",
        source_key=f"outcome:{outcome_record.outcome_intake_id}",
        title="Опубликован результат закупки",
        body=f"Статус: {payload.outcome_code}",
        deal_id=payload.deal_id,
    )
    session.refresh(outcome_set)
    return outcome_set


def get_outcome_intake_set(
    session: Session,
    outcome_intake_set_id: str,
) -> tuple[OutcomeIntakeSet, list[tuple[OutcomeIntakeRecord, list[OutcomeIntakeBinding]]]]:
    outcome_set = _get_set(session, outcome_intake_set_id)
    records = _get_records(session, outcome_intake_set_id)
    return outcome_set, [(record, _get_bindings(session, record.outcome_intake_id)) for record in records]


def list_outcome_intake_sets(
    session: Session,
    *,
    deal_id: str | None = None,
) -> list[tuple[OutcomeIntakeSet, list[tuple[OutcomeIntakeRecord, list[OutcomeIntakeBinding]]]]]:
    query = select(OutcomeIntakeSet).order_by(OutcomeIntakeSet.created_at.desc())
    if deal_id:
        query = query.where(OutcomeIntakeSet.deal_id == deal_id)
    sets = list(session.scalars(query))
    return [get_outcome_intake_set(session, item.outcome_intake_set_id) for item in sets]


def get_outcome_intake_record(
    session: Session,
    outcome_intake_id: str,
) -> tuple[OutcomeIntakeRecord, list[OutcomeIntakeBinding]]:
    record = _get_record(session, outcome_intake_id)
    return record, _get_bindings(session, outcome_intake_id)
