from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.bid_completeness.service import get_bid_completeness_set
from src.modules.ceo_approval.service import get_ceo_approval_set
from src.modules.event_log.service import append_event_record
from src.modules.finance_memo.service import get_finance_memo_set
from src.modules.integrated_risk_memo.service import get_integrated_risk_memo_set
from src.modules.submission_readiness.models import (
    SubmissionReadinessFlag,
    SubmissionReadinessRecord,
    SubmissionReadinessSet,
)
from src.modules.submission_readiness.schemas import BuildSubmissionReadinessRequest
from src.shared.db.base import utcnow
from src.shared.enums import (
    ApprovalDecision,
    ApprovalStatus,
    BidCompletenessStatus,
    EventSeverity,
    FinanceRecommendation,
    ReadinessRecommendation,
    RiskSeverity,
    SubmissionReadinessStatus,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.ids import next_submission_readiness_id, next_submission_readiness_set_id
from src.shared.validation import require_same_reference


def _get_set(session: Session, submission_readiness_set_id: str) -> SubmissionReadinessSet:
    record = session.scalar(
        select(SubmissionReadinessSet).where(
            SubmissionReadinessSet.submission_readiness_set_id == submission_readiness_set_id
        )
    )
    if not record:
        raise NotFoundError(f"Submission readiness set '{submission_readiness_set_id}' was not found")
    return record


def _get_records(session: Session, submission_readiness_set_id: str) -> list[SubmissionReadinessRecord]:
    return list(
        session.scalars(
            select(SubmissionReadinessRecord)
            .where(SubmissionReadinessRecord.submission_readiness_set_id == submission_readiness_set_id)
            .order_by(SubmissionReadinessRecord.created_at.asc(), SubmissionReadinessRecord.id.asc())
        )
    )


def _get_flags(session: Session, submission_readiness_id: str) -> list[SubmissionReadinessFlag]:
    return list(
        session.scalars(
            select(SubmissionReadinessFlag)
            .where(SubmissionReadinessFlag.submission_readiness_id == submission_readiness_id)
            .order_by(SubmissionReadinessFlag.created_at.asc(), SubmissionReadinessFlag.id.asc())
        )
    )


def _merge_recommendations(*values: str) -> str:
    if any(value == str(ReadinessRecommendation.NOT_READY) for value in values):
        return str(ReadinessRecommendation.NOT_READY)
    if any(value == str(ReadinessRecommendation.NEEDS_REVIEW) for value in values):
        return str(ReadinessRecommendation.NEEDS_REVIEW)
    return str(ReadinessRecommendation.READY)


def build_submission_readiness(session: Session, payload: BuildSubmissionReadinessRequest) -> SubmissionReadinessSet:
    completeness_set, completeness_records, _readiness_reports = get_bid_completeness_set(
        session, payload.bid_completeness_set_id
    )
    approval_set, approval_records = get_ceo_approval_set(session, payload.ceo_approval_set_id)
    finance_set, finance_records = get_finance_memo_set(session, payload.finance_memo_set_id)
    risk_set, risk_records = get_integrated_risk_memo_set(session, payload.integrated_risk_memo_set_id)

    for actual_deal_id in (
        completeness_set.deal_id,
        approval_set.deal_id,
        finance_set.deal_id,
        risk_set.deal_id,
    ):
        require_same_reference(payload.deal_id, actual_deal_id, "deal_id")

    if not completeness_records or not finance_records or not risk_records:
        raise ValidationError("Submission readiness requires persisted completeness, finance, and risk records")

    completeness_record, completeness_flags = completeness_records[0]
    finance_record, finance_flags = finance_records[0]
    risk_record, risk_items = risk_records[0]
    latest_approval = approval_records[-1][0] if approval_records else None

    readiness_set = SubmissionReadinessSet(
        submission_readiness_set_id=next_submission_readiness_set_id(
            session, SubmissionReadinessSet.submission_readiness_set_id
        ),
        deal_id=payload.deal_id,
        bid_completeness_set_id=completeness_set.bid_completeness_set_id,
        ceo_approval_set_id=approval_set.ceo_approval_set_id,
        finance_memo_set_id=finance_set.finance_memo_set_id,
        integrated_risk_memo_set_id=risk_set.integrated_risk_memo_set_id,
        readiness_status=SubmissionReadinessStatus.READY,
    )
    session.add(readiness_set)
    session.flush()
    append_event_record(
        session,
        deal_id=payload.deal_id,
        event_code="submission_readiness_build_started",
        source_module_id="M-032",
        severity=EventSeverity.INFO,
        payload_json={"submission_readiness_set_id": readiness_set.submission_readiness_set_id},
    )
    try:
        flags_data: list[dict] = []

        completeness_recommendation = str(ReadinessRecommendation.READY)
        if str(completeness_set.completeness_status) == str(BidCompletenessStatus.INCOMPLETE):
            completeness_recommendation = str(ReadinessRecommendation.NOT_READY)
            flags_data.append(
                {
                    "flag_code": "INCOMPLETE_BID_PACKAGE",
                    "severity": RiskSeverity.HIGH,
                    "summary": completeness_record.summary_text,
                    "source_ref": completeness_set.bid_completeness_set_id,
                }
            )
        elif str(completeness_set.completeness_status) == str(BidCompletenessStatus.NEEDS_REVIEW):
            completeness_recommendation = str(ReadinessRecommendation.NEEDS_REVIEW)
            flags_data.append(
                {
                    "flag_code": "BID_PACKAGE_NEEDS_REVIEW",
                    "severity": RiskSeverity.MEDIUM,
                    "summary": completeness_record.summary_text,
                    "source_ref": completeness_set.bid_completeness_set_id,
                }
            )

        approval_recommendation = str(ReadinessRecommendation.READY)
        if approval_set.approval_status != ApprovalStatus.DECIDED or latest_approval is None:
            approval_recommendation = str(ReadinessRecommendation.NOT_READY)
            flags_data.append(
                {
                    "flag_code": "CEO_DECISION_MISSING",
                    "severity": RiskSeverity.HIGH,
                    "summary": "No explicit CEO decision is persisted for the approval package.",
                    "source_ref": approval_set.ceo_approval_set_id,
                }
            )
        elif str(latest_approval.decision) == str(ApprovalDecision.NO_GO):
            approval_recommendation = str(ReadinessRecommendation.NOT_READY)
            flags_data.append(
                {
                    "flag_code": "CEO_DECISION_NO_GO",
                    "severity": RiskSeverity.CRITICAL,
                    "summary": "CEO decision is NO_GO, so submission readiness is blocked.",
                    "source_ref": latest_approval.ceo_approval_id,
                }
            )
        elif str(latest_approval.decision) in {
            str(ApprovalDecision.GO_WITH_CONDITIONS),
            str(ApprovalDecision.NEEDS_REVIEW),
        }:
            approval_recommendation = str(ReadinessRecommendation.NEEDS_REVIEW)
            flags_data.append(
                {
                    "flag_code": "CEO_DECISION_CONDITIONAL",
                    "severity": RiskSeverity.MEDIUM,
                    "summary": "CEO decision requires conditions or further review before submission.",
                    "source_ref": latest_approval.ceo_approval_id,
                }
            )

        finance_recommendation = str(ReadinessRecommendation.READY)
        if str(finance_record.recommendation) == str(FinanceRecommendation.NO_GO):
            finance_recommendation = str(ReadinessRecommendation.NOT_READY)
            flags_data.append(
                {
                    "flag_code": "FINANCE_NO_GO",
                    "severity": RiskSeverity.CRITICAL,
                    "summary": finance_record.summary_text,
                    "source_ref": finance_record.finance_memo_id,
                }
            )
        elif str(finance_record.recommendation) in {
            str(FinanceRecommendation.GO_WITH_CONDITIONS),
            str(FinanceRecommendation.NEEDS_REVIEW),
        }:
            finance_recommendation = str(ReadinessRecommendation.NEEDS_REVIEW)
            flags_data.append(
                {
                    "flag_code": "FINANCE_CONDITIONAL",
                    "severity": RiskSeverity.MEDIUM,
                    "summary": finance_record.summary_text,
                    "source_ref": finance_record.finance_memo_id,
                }
            )

        risk_recommendation = str(ReadinessRecommendation.READY)
        if str(risk_record.recommendation) == str(ApprovalDecision.NO_GO):
            risk_recommendation = str(ReadinessRecommendation.NOT_READY)
            flags_data.append(
                {
                    "flag_code": "RISK_MEMO_NO_GO",
                    "severity": RiskSeverity.CRITICAL,
                    "summary": risk_record.summary_text,
                    "source_ref": risk_record.integrated_risk_memo_id,
                }
            )
        elif str(risk_record.recommendation) in {
            str(ApprovalDecision.GO_WITH_CONDITIONS),
            str(ApprovalDecision.NEEDS_REVIEW),
        }:
            risk_recommendation = str(ReadinessRecommendation.NEEDS_REVIEW)
            flags_data.append(
                {
                    "flag_code": "RISK_MEMO_CONDITIONAL",
                    "severity": RiskSeverity.MEDIUM,
                    "summary": risk_record.summary_text,
                    "source_ref": risk_record.integrated_risk_memo_id,
                }
            )

        recommendation = _merge_recommendations(
            completeness_recommendation,
            approval_recommendation,
            finance_recommendation,
            risk_recommendation,
        )
        readiness_status = SubmissionReadinessStatus(recommendation)
        summary_text = (
            f"Readiness recommendation: {recommendation}. "
            f"Completeness={completeness_set.completeness_status}, "
            f"CEO approval={approval_set.approval_status}, "
            f"finance={finance_record.recommendation}, "
            f"risk={risk_record.recommendation}. "
            f"Flags={len(flags_data)}."
        )

        record = SubmissionReadinessRecord(
            submission_readiness_id=next_submission_readiness_id(
                session, SubmissionReadinessRecord.submission_readiness_id
            ),
            submission_readiness_set_id=readiness_set.submission_readiness_set_id,
            recommendation=recommendation,
            summary_text=summary_text,
        )
        session.add(record)
        session.flush()
        for flag_data in flags_data:
            session.add(SubmissionReadinessFlag(submission_readiness_id=record.submission_readiness_id, **flag_data))
        readiness_set.readiness_status = readiness_status
        readiness_set.updated_at = utcnow()
        session.add(readiness_set)
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="submission_readiness_built",
            source_module_id="M-032",
            severity=EventSeverity.INFO,
            payload_json={
                "submission_readiness_set_id": readiness_set.submission_readiness_set_id,
                "submission_readiness_id": record.submission_readiness_id,
                "recommendation": recommendation,
            },
        )
        if recommendation == str(ReadinessRecommendation.NEEDS_REVIEW):
            from src.modules.integration_outbox.service import enqueue_event
            enqueue_event(session, event_type="review_required", aggregate_type="deal", aggregate_id=payload.deal_id, source_key=record.submission_readiness_id, data={"submission_readiness_id": record.submission_readiness_id, "recommendation": recommendation})
        session.commit()
    except Exception as exc:
        readiness_set.readiness_status = SubmissionReadinessStatus.NOT_READY
        readiness_set.updated_at = utcnow()
        session.add(readiness_set)
        append_event_record(
            session,
            deal_id=payload.deal_id,
            event_code="submission_readiness_failed",
            source_module_id="M-032",
            severity=EventSeverity.HIGH,
            payload_json={"submission_readiness_set_id": readiness_set.submission_readiness_set_id, "error": str(exc)},
        )
        session.commit()
        raise
    session.refresh(readiness_set)
    return readiness_set


def get_submission_readiness_set(
    session: Session,
    submission_readiness_set_id: str,
) -> tuple[SubmissionReadinessSet, list[tuple[SubmissionReadinessRecord, list[SubmissionReadinessFlag]]]]:
    readiness_set = _get_set(session, submission_readiness_set_id)
    records = _get_records(session, submission_readiness_set_id)
    return readiness_set, [(record, _get_flags(session, record.submission_readiness_id)) for record in records]


def list_submission_readiness_sets(
    session: Session,
    *,
    deal_id: str | None = None,
) -> list[tuple[SubmissionReadinessSet, list[tuple[SubmissionReadinessRecord, list[SubmissionReadinessFlag]]]]]:
    query = select(SubmissionReadinessSet).order_by(SubmissionReadinessSet.created_at.desc())
    if deal_id:
        query = query.where(SubmissionReadinessSet.deal_id == deal_id)
    sets = list(session.scalars(query))
    return [get_submission_readiness_set(session, item.submission_readiness_set_id) for item in sets]


def get_submission_readiness_record(
    session: Session,
    submission_readiness_id: str,
) -> tuple[SubmissionReadinessRecord, list[SubmissionReadinessFlag]]:
    record = session.scalar(
        select(SubmissionReadinessRecord).where(
            SubmissionReadinessRecord.submission_readiness_id == submission_readiness_id
        )
    )
    if not record:
        raise NotFoundError(f"Submission readiness record '{submission_readiness_id}' was not found")
    return record, _get_flags(session, submission_readiness_id)
