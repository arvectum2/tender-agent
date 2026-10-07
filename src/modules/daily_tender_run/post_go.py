from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.bid_completeness.models import BidCompletenessSet
from src.modules.bid_packages.models import BidPackageSet
from src.modules.ceo_approval.models import CEOApprovalSet
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.event_log.models import DecisionRecord
from src.modules.finance_memo.models import FinanceMemoSet
from src.modules.integrated_risk_memo.models import IntegratedRiskMemoSet
from src.modules.outcome_intake.models import (
    OutcomeIntakeBinding,
    OutcomeIntakeRecord,
    OutcomeIntakeSet,
)
from src.modules.post_submission.models import PostSubmissionTrackerSet
from src.modules.post_submission.schemas import BuildPostSubmissionTrackerRequest
from src.modules.post_submission.service import build_post_submission_tracker
from src.modules.submission_control.models import (
    SubmissionAttempt,
    SubmissionExecutionRecord,
    SubmissionExecutionSet,
)
from src.modules.submission_control.schemas import BuildSubmissionControlRequest
from src.modules.submission_control.service import build_submission_control
from src.modules.submission_readiness.models import (
    SubmissionReadinessRecord,
    SubmissionReadinessSet,
)
from src.modules.submission_readiness.schemas import BuildSubmissionReadinessRequest
from src.modules.submission_readiness.service import build_submission_readiness
from src.modules.submission_receipts.models import (
    SubmissionReceiptBinding,
    SubmissionReceiptRecord,
    SubmissionReceiptSet,
)
from src.shared.db.base import utcnow
from src.shared.enums import (
    DecisionByType,
    ReadinessRecommendation,
    SubmissionAttemptStatus,
    SubmissionExecutionStatus,
    SubmissionReceiptStatus,
)

_ACTIVE_STATUSES = {
    "MANAGER_READY",
    "DEFERRED",
    "DECIDED_NO_GO",
    "POST_DECISION",
    "READINESS_BLOCKED",
    "AWAITING_SUBMISSION_EVIDENCE",
    "AWAITING_OUTCOME_EVIDENCE",
    "POST_DECISION_FAILED",
}


def _latest_for_deal(session: Session, model, deal_id: str):
    return session.scalar(
        select(model)
        .where(model.deal_id == deal_id)
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(1)
    )


def _latest_human_decision(
    session: Session,
    deal_id: str,
) -> tuple[DecisionRecord | None, str | None]:
    record = session.scalar(
        select(DecisionRecord)
        .where(
            DecisionRecord.deal_id == deal_id,
            DecisionRecord.decision_code == "PORTFOLIO_BID_DECISION",
            DecisionRecord.decided_by_type == str(DecisionByType.HUMAN),
        )
        .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
        .limit(1)
    )
    if record is None:
        return None, None
    payload = record.payload_json or {}
    mobile_action = str(payload.get("mobile_action") or "").strip().upper()
    if mobile_action in {"GO", "NO_GO", "DEFER"}:
        return record, mobile_action

    decision = str(payload.get("decision") or "").strip().upper()
    if decision in {"GO", "GO_WITH_CONDITIONS"}:
        return record, "GO"
    if decision == "NO_GO":
        return record, "NO_GO"
    if decision == "NEEDS_REVIEW" and payload.get("deferred_until"):
        return record, "DEFER"
    return record, None


def _item_state(item: DailyTenderRunItem) -> dict[str, Any]:
    return dict(item.post_decision_json or {})


def _persist_item(
    session: Session,
    item: DailyTenderRunItem,
    *,
    stage: str | None = None,
    status: str | None = None,
    state: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if stage is not None:
        item.stage = stage
    if status is not None:
        item.status = status
    if state is not None:
        item.post_decision_json = state
    item.error = error
    item.updated_at = utcnow()
    session.add(item)
    session.commit()


def _human_state(record: DecisionRecord, action: str) -> dict[str, Any]:
    payload = record.payload_json or {}
    return {
        "action": action,
        "decision_id": record.decision_id,
        "decided_by_ref": record.decided_by_ref,
        "decided_at": record.created_at.isoformat(),
        "rationale": record.rationale,
        "reason_codes": list(payload.get("reason_codes") or []),
        "deferred_until": payload.get("deferred_until"),
    }


def _latest_readiness_record(
    session: Session,
    readiness_set: SubmissionReadinessSet,
) -> SubmissionReadinessRecord | None:
    return session.scalar(
        select(SubmissionReadinessRecord)
        .where(
            SubmissionReadinessRecord.submission_readiness_set_id
            == readiness_set.submission_readiness_set_id
        )
        .order_by(
            SubmissionReadinessRecord.created_at.desc(),
            SubmissionReadinessRecord.id.desc(),
        )
        .limit(1)
    )


def _ensure_readiness(
    session: Session,
    item: DailyTenderRunItem,
    state: dict[str, Any],
) -> SubmissionReadinessSet | None:
    assert item.deal_id
    completeness = _latest_for_deal(session, BidCompletenessSet, item.deal_id)
    approval = _latest_for_deal(session, CEOApprovalSet, item.deal_id)
    finance = (
        session.scalar(
            select(FinanceMemoSet).where(
                FinanceMemoSet.finance_memo_set_id == approval.finance_memo_set_id
            )
        )
        if approval is not None
        else None
    )
    risk = (
        session.scalar(
            select(IntegratedRiskMemoSet).where(
                IntegratedRiskMemoSet.integrated_risk_memo_set_id
                == approval.integrated_risk_memo_set_id
            )
        )
        if approval is not None
        else None
    )
    missing = [
        name
        for name, value in (
            ("bid_completeness", completeness),
            ("ceo_approval", approval),
            ("finance_memo", finance),
            ("integrated_risk_memo", risk),
        )
        if value is None
    ]
    if missing:
        state["readiness"] = {
            "status": "BLOCKED",
            "reason": "missing_canonical_prerequisites",
            "missing": missing,
        }
        _persist_item(
            session,
            item,
            stage="POST_DECISION",
            status="READINESS_BLOCKED",
            state=state,
        )
        return None

    readiness_set = session.scalar(
        select(SubmissionReadinessSet)
        .where(
            SubmissionReadinessSet.deal_id == item.deal_id,
            SubmissionReadinessSet.bid_completeness_set_id
            == completeness.bid_completeness_set_id,
            SubmissionReadinessSet.ceo_approval_set_id
            == approval.ceo_approval_set_id,
            SubmissionReadinessSet.finance_memo_set_id
            == finance.finance_memo_set_id,
            SubmissionReadinessSet.integrated_risk_memo_set_id
            == risk.integrated_risk_memo_set_id,
        )
        .order_by(
            SubmissionReadinessSet.created_at.desc(),
            SubmissionReadinessSet.id.desc(),
        )
        .limit(1)
    )
    if readiness_set is None:
        readiness_set = build_submission_readiness(
            session,
            BuildSubmissionReadinessRequest(
                deal_id=item.deal_id,
                bid_completeness_set_id=completeness.bid_completeness_set_id,
                ceo_approval_set_id=approval.ceo_approval_set_id,
                finance_memo_set_id=finance.finance_memo_set_id,
                integrated_risk_memo_set_id=risk.integrated_risk_memo_set_id,
            ),
        )

    record = _latest_readiness_record(session, readiness_set)
    recommendation = (
        str(record.recommendation)
        if record is not None
        else str(readiness_set.readiness_status)
    )
    state["readiness"] = {
        "status": recommendation,
        "submission_readiness_set_id": readiness_set.submission_readiness_set_id,
        "summary": record.summary_text if record is not None else None,
        "source_refs": {
            "bid_completeness_set_id": completeness.bid_completeness_set_id,
            "ceo_approval_set_id": approval.ceo_approval_set_id,
            "finance_memo_set_id": finance.finance_memo_set_id,
            "integrated_risk_memo_set_id": risk.integrated_risk_memo_set_id,
        },
    }
    if recommendation != str(ReadinessRecommendation.READY):
        state["readiness"]["reason"] = "readiness_requires_human_resolution"
        _persist_item(
            session,
            item,
            stage="POST_DECISION",
            status="READINESS_BLOCKED",
            state=state,
        )
        return None
    return readiness_set


def _ensure_submission_control(
    session: Session,
    item: DailyTenderRunItem,
    readiness_set: SubmissionReadinessSet,
    state: dict[str, Any],
) -> SubmissionExecutionSet:
    assert item.deal_id
    completeness = session.scalar(
        select(BidCompletenessSet).where(
            BidCompletenessSet.bid_completeness_set_id
            == readiness_set.bid_completeness_set_id
        )
    )
    if completeness is None:
        raise RuntimeError("Readiness references a missing bid completeness set")
    package = session.scalar(
        select(BidPackageSet).where(
            BidPackageSet.bid_package_set_id == completeness.bid_package_set_id
        )
    )
    if package is None:
        raise RuntimeError("Bid completeness references a missing bid package set")

    execution_set = session.scalar(
        select(SubmissionExecutionSet)
        .where(
            SubmissionExecutionSet.deal_id == item.deal_id,
            SubmissionExecutionSet.submission_readiness_set_id
            == readiness_set.submission_readiness_set_id,
            SubmissionExecutionSet.bid_package_set_id == package.bid_package_set_id,
        )
        .order_by(
            SubmissionExecutionSet.created_at.desc(),
            SubmissionExecutionSet.id.desc(),
        )
        .limit(1)
    )
    if execution_set is None:
        execution_set = build_submission_control(
            session,
            BuildSubmissionControlRequest(
                deal_id=item.deal_id,
                submission_readiness_set_id=readiness_set.submission_readiness_set_id,
                bid_package_set_id=package.bid_package_set_id,
            ),
        )
    state["submission"] = {
        "submission_execution_set_id": execution_set.submission_execution_set_id,
        "status": str(execution_set.execution_status),
        "evidence_status": "PENDING",
    }
    return execution_set


def _verified_submission_evidence(
    session: Session,
    execution_set: SubmissionExecutionSet,
) -> dict[str, Any] | None:
    succeeded = list(
        session.execute(
            select(SubmissionExecutionRecord, SubmissionAttempt)
            .join(
                SubmissionAttempt,
                SubmissionAttempt.submission_execution_id
                == SubmissionExecutionRecord.submission_execution_id,
            )
            .where(
                SubmissionExecutionRecord.submission_execution_set_id
                == execution_set.submission_execution_set_id,
                SubmissionAttempt.attempt_status
                == str(SubmissionAttemptStatus.SUCCEEDED),
            )
            .order_by(
                SubmissionAttempt.created_at.desc(),
                SubmissionAttempt.id.desc(),
            )
        )
    )
    for execution_record, attempt in succeeded:
        actor = str(execution_record.initiated_by_ref or "").strip()
        if actor:
            return {
                "kind": "explicit_human_execution",
                "submission_execution_id": execution_record.submission_execution_id,
                "submission_attempt_id": attempt.submission_attempt_id,
                "initiated_by_ref": actor,
                "recorded_at": attempt.created_at.isoformat(),
            }

    receipt = session.execute(
        select(
            SubmissionReceiptSet,
            SubmissionReceiptRecord,
            SubmissionReceiptBinding,
        )
        .join(
            SubmissionReceiptRecord,
            SubmissionReceiptRecord.submission_receipt_set_id
            == SubmissionReceiptSet.submission_receipt_set_id,
        )
        .join(
            SubmissionReceiptBinding,
            SubmissionReceiptBinding.submission_receipt_id
            == SubmissionReceiptRecord.submission_receipt_id,
        )
        .where(
            SubmissionReceiptSet.submission_execution_set_id
            == execution_set.submission_execution_set_id,
            SubmissionReceiptSet.receipt_status
            == str(SubmissionReceiptStatus.REGISTERED),
        )
        .order_by(
            SubmissionReceiptRecord.receipt_timestamp.desc(),
            SubmissionReceiptBinding.created_at.desc(),
        )
        .limit(1)
    ).first()
    if receipt is not None:
        receipt_set, receipt_record, binding = receipt
        return {
            "kind": "source_bound_receipt",
            "submission_receipt_set_id": receipt_set.submission_receipt_set_id,
            "submission_receipt_id": receipt_record.submission_receipt_id,
            "receipt_number": receipt_record.receipt_number,
            "receipt_source": str(receipt_record.receipt_source),
            "artifact_ref": binding.artifact_ref,
            "recorded_at": receipt_record.receipt_timestamp.isoformat(),
        }
    return None


def _ensure_post_submission_tracker(
    session: Session,
    item: DailyTenderRunItem,
    execution_set: SubmissionExecutionSet,
) -> PostSubmissionTrackerSet:
    assert item.deal_id
    tracker = session.scalar(
        select(PostSubmissionTrackerSet)
        .where(
            PostSubmissionTrackerSet.deal_id == item.deal_id,
            PostSubmissionTrackerSet.submission_execution_set_id
            == execution_set.submission_execution_set_id,
        )
        .order_by(
            PostSubmissionTrackerSet.created_at.desc(),
            PostSubmissionTrackerSet.id.desc(),
        )
        .limit(1)
    )
    if tracker is None:
        tracker = build_post_submission_tracker(
            session,
            BuildPostSubmissionTrackerRequest(
                deal_id=item.deal_id,
                submission_execution_set_id=execution_set.submission_execution_set_id,
                summary_text=(
                    "Grounded submission evidence detected by Daily Tender Run; "
                    "post-submission tracking opened."
                ),
            ),
        )
    return tracker


def _grounded_outcome(
    session: Session,
    *,
    deal_id: str,
    tracker: PostSubmissionTrackerSet,
) -> tuple[OutcomeIntakeSet, OutcomeIntakeRecord, OutcomeIntakeBinding] | None:
    row = session.execute(
        select(OutcomeIntakeSet, OutcomeIntakeRecord, OutcomeIntakeBinding)
        .join(
            OutcomeIntakeRecord,
            OutcomeIntakeRecord.outcome_intake_set_id
            == OutcomeIntakeSet.outcome_intake_set_id,
        )
        .join(
            OutcomeIntakeBinding,
            OutcomeIntakeBinding.outcome_intake_id
            == OutcomeIntakeRecord.outcome_intake_id,
        )
        .where(
            OutcomeIntakeSet.deal_id == deal_id,
            OutcomeIntakeSet.post_submission_tracker_set_id
            == tracker.post_submission_tracker_set_id,
        )
        .order_by(
            OutcomeIntakeRecord.effective_at.desc(),
            OutcomeIntakeRecord.id.desc(),
            OutcomeIntakeBinding.created_at.desc(),
        )
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


def _advance_go(
    session: Session,
    item: DailyTenderRunItem,
    state: dict[str, Any],
) -> None:
    readiness_set = _ensure_readiness(session, item, state)
    if readiness_set is None:
        return

    execution_set = _ensure_submission_control(
        session,
        item,
        readiness_set,
        state,
    )
    if str(execution_set.execution_status) != str(SubmissionExecutionStatus.SUBMITTED):
        state["submission"]["status"] = str(execution_set.execution_status)
        state["submission"]["evidence_status"] = "PENDING"
        _persist_item(
            session,
            item,
            stage="TRACK_SUBMISSION",
            status="AWAITING_SUBMISSION_EVIDENCE",
            state=state,
        )
        return

    evidence = _verified_submission_evidence(session, execution_set)
    if evidence is None:
        state["submission"]["status"] = str(execution_set.execution_status)
        state["submission"]["evidence_status"] = "UNVERIFIED"
        _persist_item(
            session,
            item,
            stage="TRACK_SUBMISSION",
            status="AWAITING_SUBMISSION_EVIDENCE",
            state=state,
        )
        return

    state["submission"]["status"] = str(execution_set.execution_status)
    state["submission"]["evidence_status"] = "VERIFIED"
    state["submission"]["evidence"] = evidence
    tracker = _ensure_post_submission_tracker(session, item, execution_set)
    state["submission"]["post_submission_tracker_set_id"] = (
        tracker.post_submission_tracker_set_id
    )

    grounded = _grounded_outcome(
        session,
        deal_id=item.deal_id,
        tracker=tracker,
    )
    if grounded is None:
        state["outcome"] = {
            "status": "PENDING_GROUNDED_EVIDENCE",
            "post_submission_tracker_set_id": tracker.post_submission_tracker_set_id,
        }
        _persist_item(
            session,
            item,
            stage="TRACK_OUTCOME",
            status="AWAITING_OUTCOME_EVIDENCE",
            state=state,
        )
        return

    outcome_set, outcome_record, binding = grounded
    state["outcome"] = {
        "status": "GROUNDED",
        "outcome_intake_set_id": outcome_set.outcome_intake_set_id,
        "outcome_intake_id": outcome_record.outcome_intake_id,
        "code": str(outcome_record.outcome_code),
        "effective_at": outcome_record.effective_at.isoformat(),
        "rationale": outcome_record.rationale,
        "artifact_ref": binding.artifact_ref,
        "binding_type": str(binding.binding_type),
    }
    _persist_item(
        session,
        item,
        stage="DONE",
        status="OUTCOME_RECORDED",
        state=state,
    )


def _advance_item(session: Session, item: DailyTenderRunItem) -> None:
    if not item.deal_id:
        return
    decision, action = _latest_human_decision(session, item.deal_id)
    if decision is None or action is None:
        return

    state = _item_state(item)
    state["human_decision"] = _human_state(decision, action)
    item.human_decision = action
    item.human_decision_id = decision.decision_id

    if action == "DEFER":
        _persist_item(
            session,
            item,
            stage="WAIT_HUMAN",
            status="DEFERRED",
            state=state,
        )
        return
    if action == "NO_GO":
        state["post_decision"] = {
            "status": "STOPPED",
            "reason": "human_no_go",
        }
        _persist_item(
            session,
            item,
            stage="DONE",
            status="DECIDED_NO_GO",
            state=state,
        )
        return

    item.stage = "POST_DECISION"
    item.status = "POST_DECISION"
    _persist_item(session, item, state=state)
    _advance_go(session, item, state)


def advance_post_decision_items(
    session: Session,
    run: DailyTenderRun,
) -> None:
    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(
                DailyTenderRunItem.run_id == run.run_id,
                DailyTenderRunItem.status.in_(tuple(_ACTIVE_STATUSES)),
            )
            .order_by(
                DailyTenderRunItem.created_at.asc(),
                DailyTenderRunItem.id.asc(),
            )
        )
    )
    for item in items:
        try:
            _advance_item(session, item)
        except Exception as exc:  # noqa: BLE001 - one case must not stop the run
            session.rollback()
            fresh = session.get(DailyTenderRunItem, item.id)
            if fresh is None:
                continue
            state = _item_state(fresh)
            state["last_error"] = {
                "type": type(exc).__name__,
                "message": str(exc)[:2000],
                "at": datetime.now().astimezone().isoformat(),
            }
            _persist_item(
                session,
                fresh,
                stage=fresh.stage or "POST_DECISION",
                status="POST_DECISION_FAILED",
                state=state,
                error=f"{type(exc).__name__}: {exc}"[:4000],
            )
