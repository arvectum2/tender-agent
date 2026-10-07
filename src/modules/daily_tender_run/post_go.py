from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.bid_completeness.service import list_bid_completeness_sets
from src.modules.bid_documents.service import list_bid_document_collection_sets
from src.modules.bid_packages.schemas import BuildBidPackageRequest
from src.modules.bid_packages.service import build_bid_package, list_bid_package_sets
from src.modules.ceo_approval.service import list_ceo_approval_sets
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.event_log.models import DecisionRecord
from src.modules.event_log.service import append_event_record
from src.modules.finance_memo.service import list_finance_memo_sets
from src.modules.integrated_risk_memo.service import list_integrated_risk_memo_sets
from src.modules.outcome_intake.service import list_outcome_intake_sets
from src.modules.post_submission.schemas import BuildPostSubmissionTrackerRequest
from src.modules.post_submission.service import (
    build_post_submission_tracker,
    list_post_submission_tracker_sets,
)
from src.modules.submission_control.schemas import BuildSubmissionControlRequest
from src.modules.submission_control.service import (
    build_submission_control,
    list_submission_execution_sets,
)
from src.modules.submission_readiness.schemas import BuildSubmissionReadinessRequest
from src.modules.submission_readiness.service import (
    build_submission_readiness,
    list_submission_readiness_sets,
)
from src.shared.db.base import utcnow
from src.shared.enums import DecisionByType, EventSeverity


_HUMAN_DECISION_CODES = {
    "PORTFOLIO_BID_DECISION",
    "CEO_APPROVAL_DECISION",
    "APPROVE_TO_BID",
    "DECLINE_TO_BID",
    "DEAL_MARKED_REJECTED_EARLY",
    "OPERATOR_REJECTED_PREBID",
    "OPERATOR_MARKED_NEEDS_MORE_REVIEW",
}

_ACTIVE_STATUSES = {
    "MANAGER_READY",
    "DEFERRED",
    "READINESS_BLOCKED",
    "AWAITING_SUBMISSION_EVIDENCE",
    "AWAITING_OUTCOME_EVIDENCE",
    "POST_GO_FAILED",
}


def _first_set(rows: list[Any]) -> Any | None:
    return rows[0][0] if rows else None


def _decision_action(record: DecisionRecord) -> str | None:
    payload = record.payload_json or {}
    if record.decision_code in {"PORTFOLIO_BID_DECISION", "CEO_APPROVAL_DECISION"}:
        if str(payload.get("mobile_action") or "").upper() == "DEFER":
            return "DEFER"
        value = str(payload.get("decision") or "").upper()
        if value in {"GO", "GO_WITH_CONDITIONS"}:
            return "GO"
        if value in {"NO_GO", "NEEDS_REVIEW"}:
            return value
        return None
    if record.decision_code == "APPROVE_TO_BID":
        return "GO"
    if record.decision_code in {
        "DECLINE_TO_BID",
        "DEAL_MARKED_REJECTED_EARLY",
        "OPERATOR_REJECTED_PREBID",
    }:
        return "NO_GO"
    if record.decision_code == "OPERATOR_MARKED_NEEDS_MORE_REVIEW":
        return "NEEDS_REVIEW"
    return None


def latest_human_decision(session: Session, deal_id: str) -> dict[str, Any] | None:
    rows = list(
        session.scalars(
            select(DecisionRecord)
            .where(
                DecisionRecord.deal_id == deal_id,
                DecisionRecord.decision_code.in_(_HUMAN_DECISION_CODES),
                DecisionRecord.decided_by_type == DecisionByType.HUMAN,
            )
            .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
        )
    )
    for row in rows:
        action = _decision_action(row)
        if action is None:
            continue
        payload = row.payload_json or {}
        return {
            "decision_id": row.decision_id,
            "action": action,
            "decided_by_ref": row.decided_by_ref,
            "rationale": row.rationale,
            "reason_codes": list(payload.get("reason_codes") or []),
            "deferred_until": payload.get("deferred_until"),
            "created_at": row.created_at.isoformat(),
        }
    return None


def _ensure_bid_package(session: Session, deal_id: str) -> dict[str, Any]:
    existing = list_bid_package_sets(session, deal_id=deal_id)
    if existing:
        package = existing[0][0]
        return {
            "state": str(package.package_status),
            "bid_package_set_id": package.bid_package_set_id,
            "created": False,
        }

    collection = _first_set(list_bid_document_collection_sets(session, deal_id=deal_id))
    if collection is None:
        return {"state": "BLOCKED", "missing": ["bid_document_collection"]}

    try:
        package = build_bid_package(
            session,
            BuildBidPackageRequest(
                deal_id=deal_id,
                bid_document_collection_set_id=collection.bid_document_collection_set_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - persist a fail-closed snapshot
        session.rollback()
        return {
            "state": "BLOCKED",
            "missing": ["buildable_bid_package"],
            "error": f"{type(exc).__name__}: {exc}"[:1000],
        }
    return {
        "state": str(package.package_status),
        "bid_package_set_id": package.bid_package_set_id,
        "created": True,
    }


def _ensure_readiness(session: Session, deal_id: str) -> dict[str, Any]:
    existing = list_submission_readiness_sets(session, deal_id=deal_id)
    if existing:
        readiness = existing[0][0]
        return {
            "state": str(readiness.readiness_status),
            "submission_readiness_set_id": readiness.submission_readiness_set_id,
            "created": False,
        }

    completeness = _first_set(list_bid_completeness_sets(session, deal_id=deal_id))
    approval = _first_set(list_ceo_approval_sets(session, deal_id=deal_id))
    finance = _first_set(list_finance_memo_sets(session, deal_id=deal_id))
    risk = _first_set(list_integrated_risk_memo_sets(session, deal_id=deal_id))
    missing = []
    if completeness is None:
        missing.append("bid_completeness")
    if approval is None:
        missing.append("ceo_approval")
    if finance is None:
        missing.append("finance_memo")
    if risk is None:
        missing.append("integrated_risk_memo")
    if missing:
        return {"state": "BLOCKED", "missing": missing}

    try:
        readiness = build_submission_readiness(
            session,
            BuildSubmissionReadinessRequest(
                deal_id=deal_id,
                bid_completeness_set_id=completeness.bid_completeness_set_id,
                ceo_approval_set_id=approval.ceo_approval_set_id,
                finance_memo_set_id=finance.finance_memo_set_id,
                integrated_risk_memo_set_id=risk.integrated_risk_memo_set_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - persist a fail-closed snapshot
        session.rollback()
        return {
            "state": "BLOCKED",
            "missing": ["buildable_submission_readiness"],
            "error": f"{type(exc).__name__}: {exc}"[:1000],
        }
    return {
        "state": str(readiness.readiness_status),
        "submission_readiness_set_id": readiness.submission_readiness_set_id,
        "created": True,
    }


def _submission_state(
    session: Session,
    *,
    deal_id: str,
    readiness: dict[str, Any],
    bid_package: dict[str, Any],
) -> dict[str, Any]:
    execution_sets = list_submission_execution_sets(session, deal_id=deal_id)
    for execution_set, _records in execution_sets:
        if str(execution_set.execution_status).upper() == "SUBMITTED":
            return {
                "state": "SUBMITTED",
                "submission_execution_set_id": execution_set.submission_execution_set_id,
                "grounded": True,
            }

    if execution_sets:
        execution_set = execution_sets[0][0]
        return {
            "state": str(execution_set.execution_status),
            "submission_execution_set_id": execution_set.submission_execution_set_id,
            "grounded": False,
        }

    if readiness.get("state") != "READY" or not readiness.get(
        "submission_readiness_set_id"
    ):
        return {"state": "NOT_STARTED", "grounded": False}
    if bid_package.get("state") != "BUILT" or not bid_package.get("bid_package_set_id"):
        return {"state": "NOT_STARTED", "grounded": False}

    try:
        execution_set = build_submission_control(
            session,
            BuildSubmissionControlRequest(
                deal_id=deal_id,
                submission_readiness_set_id=readiness["submission_readiness_set_id"],
                bid_package_set_id=bid_package["bid_package_set_id"],
            ),
        )
    except Exception as exc:  # noqa: BLE001 - never infer a submission
        session.rollback()
        return {
            "state": "NOT_STARTED",
            "grounded": False,
            "error": f"{type(exc).__name__}: {exc}"[:1000],
        }
    return {
        "state": str(execution_set.execution_status),
        "submission_execution_set_id": execution_set.submission_execution_set_id,
        "grounded": False,
        "created": True,
    }


def _outcome_state(
    session: Session,
    *,
    deal_id: str,
    submission: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if submission.get("state") != "SUBMITTED":
        return {"state": "NOT_OPEN"}, {"state": "PENDING"}

    trackers = list_post_submission_tracker_sets(session, deal_id=deal_id)
    tracker = _first_set(trackers)
    if tracker is None:
        tracker = build_post_submission_tracker(
            session,
            BuildPostSubmissionTrackerRequest(
                deal_id=deal_id,
                submission_execution_set_id=submission["submission_execution_set_id"],
                summary_text=(
                    "Grounded submission evidence detected; outcome tracking opened "
                    "by Daily Tender Run."
                ),
            ),
        )
        tracker_state = {
            "state": str(tracker.tracker_status),
            "post_submission_tracker_set_id": tracker.post_submission_tracker_set_id,
            "created": True,
        }
    else:
        tracker_state = {
            "state": str(tracker.tracker_status),
            "post_submission_tracker_set_id": tracker.post_submission_tracker_set_id,
            "created": False,
        }

    outcomes = list_outcome_intake_sets(session, deal_id=deal_id)
    if not outcomes:
        return tracker_state, {"state": "PENDING"}

    outcome_set, records = outcomes[0]
    record = records[-1][0] if records else None
    if record is None:
        return tracker_state, {
            "state": str(outcome_set.outcome_status),
            "outcome_intake_set_id": outcome_set.outcome_intake_set_id,
        }
    return tracker_state, {
        "state": str(outcome_set.outcome_status),
        "outcome_intake_set_id": outcome_set.outcome_intake_set_id,
        "outcome_intake_id": record.outcome_intake_id,
        "outcome_code": str(record.outcome_code),
        "effective_at": record.effective_at.isoformat(),
        "rationale": record.rationale,
    }


def _defer_due(decision: dict[str, Any]) -> bool:
    raw = decision.get("deferred_until")
    if not raw:
        return True
    try:
        due = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due.astimezone(UTC) <= datetime.now(UTC)


def advance_post_go_item(session: Session, item: DailyTenderRunItem) -> dict[str, Any]:
    if not item.deal_id:
        return {"state": "NO_DEAL"}

    decision = latest_human_decision(session, item.deal_id)
    if decision is None:
        return {"state": "WAIT_HUMAN"}

    before = (item.stage, item.status)
    state: dict[str, Any] = {
        "human_decision": decision,
        "updated_at": datetime.now(UTC).isoformat(),
    }

    if decision["action"] == "NO_GO":
        item.stage = "DONE"
        item.status = "DECIDED_NO_GO"
        state["state"] = "DECIDED_NO_GO"
    elif decision["action"] == "DEFER":
        if _defer_due(decision):
            item.stage = "WAIT_HUMAN"
            item.status = "MANAGER_READY"
            state["state"] = "DEFER_DUE"
        else:
            item.stage = "WAIT_HUMAN"
            item.status = "DEFERRED"
            state["state"] = "DEFERRED"
    elif decision["action"] == "NEEDS_REVIEW":
        item.stage = "WAIT_HUMAN"
        item.status = "MANAGER_READY"
        state["state"] = "NEEDS_REVIEW"
    else:
        bid_package = _ensure_bid_package(session, item.deal_id)
        readiness = _ensure_readiness(session, item.deal_id)
        submission = _submission_state(
            session,
            deal_id=item.deal_id,
            readiness=readiness,
            bid_package=bid_package,
        )
        tracker, outcome = _outcome_state(
            session,
            deal_id=item.deal_id,
            submission=submission,
        )
        state.update(
            {
                "bid_package": bid_package,
                "readiness": readiness,
                "submission": submission,
                "post_submission": tracker,
                "outcome": outcome,
            }
        )
        if outcome.get("outcome_code"):
            item.stage = "DONE"
            item.status = "OUTCOME_RECORDED"
            state["state"] = "OUTCOME_RECORDED"
        elif submission.get("state") == "SUBMITTED":
            item.stage = "TRACK_OUTCOME"
            item.status = "AWAITING_OUTCOME_EVIDENCE"
            state["state"] = "AWAITING_OUTCOME_EVIDENCE"
        elif readiness.get("state") == "READY" and bid_package.get("state") == "BUILT":
            item.stage = "TRACK_SUBMISSION"
            item.status = "AWAITING_SUBMISSION_EVIDENCE"
            state["state"] = "AWAITING_SUBMISSION_EVIDENCE"
        else:
            item.stage = "POST_DECISION"
            item.status = "READINESS_BLOCKED"
            state["state"] = "READINESS_BLOCKED"

    synthesis = dict(item.synthesis_json or {})
    synthesis["post_go"] = state
    item.synthesis_json = synthesis
    item.error = None
    item.updated_at = utcnow()
    session.add(item)

    if (item.stage, item.status) != before:
        append_event_record(
            session,
            deal_id=item.deal_id,
            event_code="daily_tender_post_go_advanced",
            source_module_id="daily_tender_run",
            severity=EventSeverity.INFO,
            payload_json={
                "daily_tender_run_item_id": item.id,
                "from_stage": before[0],
                "to_stage": item.stage,
                "from_status": before[1],
                "to_status": item.status,
                "human_decision_id": decision["decision_id"],
            },
        )
    session.commit()
    return state


def _safe_advance(session: Session, item: DailyTenderRunItem) -> dict[str, Any]:
    item_id = item.id
    try:
        return advance_post_go_item(session, item)
    except Exception as exc:  # noqa: BLE001 - isolate one procurement failure
        session.rollback()
        current = session.get(DailyTenderRunItem, item_id)
        if current is None:
            return {"state": "FAILED", "error": str(exc)[:4000]}
        if current.stage not in {"POST_DECISION", "TRACK_SUBMISSION", "TRACK_OUTCOME"}:
            current.stage = "POST_DECISION"
        current.status = "POST_GO_FAILED"
        current.error = f"{type(exc).__name__}: {exc}"[:4000]
        current.updated_at = utcnow()
        session.add(current)
        session.commit()
        return {"state": "FAILED", "error": current.error}


def _counts(items: list[DailyTenderRunItem]) -> dict[str, int]:
    keys = {
        "discovered": len(items),
        "duplicates": 0,
        "screened_out": 0,
        "deep_analyzed": 0,
        "failed": 0,
        "needs_manager": 0,
        "deferred": 0,
        "readiness_blocked": 0,
        "awaiting_submission_evidence": 0,
        "awaiting_outcome_evidence": 0,
        "outcome_recorded": 0,
        "decided_no_go": 0,
        "agent_go": 0,
        "agent_no_go": 0,
        "agent_needs_review": 0,
    }
    status_keys = {
        "DUPLICATE": "duplicates",
        "SCREENED_OUT": "screened_out",
        "MANAGER_READY": "needs_manager",
        "DEFERRED": "deferred",
        "READINESS_BLOCKED": "readiness_blocked",
        "AWAITING_SUBMISSION_EVIDENCE": "awaiting_submission_evidence",
        "AWAITING_OUTCOME_EVIDENCE": "awaiting_outcome_evidence",
        "OUTCOME_RECORDED": "outcome_recorded",
        "DECIDED_NO_GO": "decided_no_go",
    }
    recommendation_keys = {
        "GO": "agent_go",
        "NO_GO": "agent_no_go",
        "NEEDS_REVIEW": "agent_needs_review",
    }
    for item in items:
        status_key = status_keys.get(item.status)
        if status_key:
            keys[status_key] += 1
        if str(item.analysis_status or "").startswith("completed"):
            keys["deep_analyzed"] += 1
        if item.status in {"FAILED", "POST_GO_FAILED"}:
            keys["failed"] += 1
        recommendation_key = recommendation_keys.get(item.agent_recommendation or "")
        if recommendation_key:
            keys[recommendation_key] += 1
    return keys


def _digest(run: DailyTenderRun, items: list[DailyTenderRunItem]) -> dict[str, Any]:
    actionable = []
    for item in items:
        if item.status != "MANAGER_READY":
            continue
        actionable.append(
            {
                "deal_id": item.deal_id,
                "registry_number": item.registry_number,
                "title": item.title,
                "customer_name": item.customer_name,
                "nmck_amount": item.nmck_amount,
                "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
                "recommendation": item.agent_recommendation,
                "confidence": item.agent_confidence,
                "rationale": item.agent_rationale,
                "strongest_reasons": list(item.strongest_reasons_json or []),
                "blockers": list(item.blockers_json or []),
                "unknowns": list(item.unknowns_json or []),
                "analysis_run_id": item.analysis_run_id,
                "analysis_report_path": item.analysis_report_path,
                "human_decision": "PENDING",
            }
        )
    actionable.sort(
        key=lambda row: (
            {"GO": 0, "NEEDS_REVIEW": 1, "NO_GO": 2}.get(row["recommendation"], 3),
            row["deadline_at"] or "9999",
            row["registry_number"],
        )
    )
    counts = _counts(items)
    return {
        "run_id": run.run_id,
        "profile_id": run.profile_id,
        "profile_version": run.profile_version,
        "counts": counts,
        "actionable": actionable,
        "human_control": {
            "decision_required": True,
            "allowed_actions": ["GO", "NO_GO", "DEFER"],
            "external_submission_allowed": False,
        },
    }


def _refresh_run(session: Session, run_id: str) -> DailyTenderRun:
    run = session.scalar(select(DailyTenderRun).where(DailyTenderRun.run_id == run_id))
    if run is None:
        raise LookupError(f"Daily Tender Run '{run_id}' was not found")

    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(DailyTenderRunItem.run_id == run_id)
            .order_by(DailyTenderRunItem.created_at.asc(), DailyTenderRunItem.id.asc())
        )
    )
    statuses = {item.status for item in items}
    run.counts_json = _counts(items)
    run.digest_json = _digest(run, items)

    if "MANAGER_READY" in statuses or "DEFERRED" in statuses:
        run.current_stage = "WAIT_HUMAN"
        run.status = "WAITING_HUMAN"
        run.completed_at = None
    elif "AWAITING_OUTCOME_EVIDENCE" in statuses:
        run.current_stage = "TRACK_OUTCOME"
        run.status = "WAITING_EVIDENCE"
        run.completed_at = None
    elif "AWAITING_SUBMISSION_EVIDENCE" in statuses:
        run.current_stage = "TRACK_SUBMISSION"
        run.status = "WAITING_EVIDENCE"
        run.completed_at = None
    elif "READINESS_BLOCKED" in statuses:
        run.current_stage = "POST_DECISION"
        run.status = "WAITING_EVIDENCE"
        run.completed_at = None
    elif "POST_GO_FAILED" in statuses or "FAILED" in statuses:
        run.current_stage = "POST_DECISION" if "POST_GO_FAILED" in statuses else "DONE"
        run.status = "COMPLETED_WITH_ERRORS"
        run.completed_at = utcnow()
    else:
        run.current_stage = "DONE"
        run.status = "COMPLETED"
        run.completed_at = utcnow()

    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def advance_post_go_for_run(session: Session, run_id: str) -> DailyTenderRun:
    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(
                DailyTenderRunItem.run_id == run_id,
                DailyTenderRunItem.status.in_(tuple(_ACTIVE_STATUSES)),
            )
            .order_by(DailyTenderRunItem.created_at.asc(), DailyTenderRunItem.id.asc())
        )
    )
    for item in items:
        _safe_advance(session, item)
    return _refresh_run(session, run_id)


def advance_post_decision_for_deal(
    session: Session,
    deal_id: str,
) -> list[dict[str, Any]]:
    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(DailyTenderRunItem.deal_id == deal_id)
            .order_by(DailyTenderRunItem.created_at.asc(), DailyTenderRunItem.id.asc())
        )
    )
    results = []
    run_ids = set()
    for item in items:
        analyzed = str(item.analysis_status or "").startswith("completed")
        if not analyzed and item.status not in _ACTIVE_STATUSES:
            continue
        results.append(_safe_advance(session, item))
        run_ids.add(item.run_id)
    for run_id in run_ids:
        _refresh_run(session, run_id)
    return results


def post_go_state(item: DailyTenderRunItem) -> dict[str, Any] | None:
    value = (item.synthesis_json or {}).get("post_go")
    return dict(value) if isinstance(value, dict) else None
