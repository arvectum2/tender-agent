from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord, EventRecord
from src.modules.event_log.schemas import AppendDecisionRequest
from src.modules.event_log.service import append_decision
from src.modules.outcome_intake.models import OutcomeIntakeRecord, OutcomeIntakeSet
from src.modules.postmortems.models import PostmortemRecord, PostmortemSet
from src.modules.submission_control.models import SubmissionExecutionSet
from src.modules.tender_intake.schemas import CreateTenderIntakeRequest
from src.modules.tender_intake.service import create_tender_intake
from src.modules.tender_screening.models import TenderScreeningRecord
from src.shared.enums import (
    DecisionByType,
    InitialSourceType,
    TenderSourceType,
)

from .schemas import CreatePortfolioProcurementRequest, RecordPortfolioDecisionRequest

_EXPLICIT_DECISION_CODES = {
    "PORTFOLIO_BID_DECISION",
    "CEO_APPROVAL_DECISION",
    "APPROVE_TO_BID",
    "DECLINE_TO_BID",
    "DEAL_MARKED_REJECTED_EARLY",
    "OPERATOR_REJECTED_PREBID",
    "OPERATOR_MARKED_NEEDS_MORE_REVIEW",
}

_STATUS_IMPLIED_NO_GO = {"DECLINED_TO_BID", "REJECTED_EARLY"}
_STATUS_IMPLIED_GO = {
    "BID_PREPARATION",
    "PRE_SUBMISSION",
    "SUBMISSION",
    "POST_SUBMISSION",
    "OUTCOME_CAPTURE",
}


def _clean_reason_codes(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _decision_from_record(record: DecisionRecord) -> str | None:
    payload = record.payload_json or {}
    if record.decision_code in {"PORTFOLIO_BID_DECISION", "CEO_APPROVAL_DECISION"}:
        value = str(payload.get("decision") or "").upper()
        if value in {"GO", "GO_WITH_CONDITIONS"}:
            return "GO"
        if value == "NO_GO":
            return "NO_GO"
        if value == "NEEDS_REVIEW":
            return "NEEDS_REVIEW"
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


def _screening_decision(screening: TenderScreeningRecord | None) -> str | None:
    if screening is None:
        return None
    value = str(screening.result_status).upper()
    if value == "PASS":
        return "GO"
    if value == "FAIL":
        return "NO_GO"
    if value == "NEEDS_REVIEW":
        return "NEEDS_REVIEW"
    return None


def _latest_by_deal(rows, deal_attr: str = "deal_id") -> dict[str, object]:
    result: dict[str, object] = {}
    for row in rows:
        result[getattr(row, deal_attr)] = row
    return result


def _portfolio_rows(session: Session) -> list[dict]:
    deals = list(
        session.scalars(
            select(Deal)
            .where(Deal.is_deleted.is_(False))
            .order_by(Deal.created_at.desc(), Deal.id.desc())
        )
    )
    if not deals:
        return []
    deal_ids = [deal.deal_id for deal in deals]

    screenings = list(
        session.scalars(
            select(TenderScreeningRecord)
            .where(TenderScreeningRecord.deal_id.in_(deal_ids))
            .order_by(TenderScreeningRecord.created_at.asc(), TenderScreeningRecord.id.asc())
        )
    )
    latest_screening = _latest_by_deal(screenings)

    decisions = list(
        session.scalars(
            select(DecisionRecord)
            .where(
                DecisionRecord.deal_id.in_(deal_ids),
                DecisionRecord.decision_code.in_(_EXPLICIT_DECISION_CODES),
            )
            .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc())
        )
    )
    latest_decision: dict[str, DecisionRecord] = {}
    for decision in decisions:
        if _decision_from_record(decision):
            latest_decision[decision.deal_id] = decision

    submission_sets = list(
        session.scalars(
            select(SubmissionExecutionSet)
            .where(SubmissionExecutionSet.deal_id.in_(deal_ids))
            .order_by(SubmissionExecutionSet.updated_at.asc(), SubmissionExecutionSet.id.asc())
        )
    )
    submitted_from_set: dict[str, datetime] = {}
    for row in submission_sets:
        if str(row.execution_status).upper() == "SUBMITTED":
            submitted_from_set[row.deal_id] = row.updated_at

    submission_events = list(
        session.scalars(
            select(EventRecord)
            .where(
                EventRecord.deal_id.in_(deal_ids),
                EventRecord.event_code == "submission_execution_submitted",
            )
            .order_by(EventRecord.created_at.asc(), EventRecord.id.asc())
        )
    )
    submitted_at = {**submitted_from_set}
    for event in submission_events:
        if event.deal_id:
            submitted_at[event.deal_id] = event.created_at

    outcome_rows = list(
        session.execute(
            select(OutcomeIntakeSet.deal_id, OutcomeIntakeRecord)
            .join(
                OutcomeIntakeRecord,
                OutcomeIntakeRecord.outcome_intake_set_id
                == OutcomeIntakeSet.outcome_intake_set_id,
            )
            .where(OutcomeIntakeSet.deal_id.in_(deal_ids))
            .order_by(OutcomeIntakeRecord.effective_at.asc(), OutcomeIntakeRecord.id.asc())
        )
    )
    latest_outcome: dict[str, OutcomeIntakeRecord] = {}
    for deal_id, record in outcome_rows:
        latest_outcome[deal_id] = record

    postmortem_rows = list(
        session.execute(
            select(PostmortemSet.deal_id, PostmortemRecord)
            .join(
                PostmortemRecord,
                PostmortemRecord.postmortem_set_id == PostmortemSet.postmortem_set_id,
            )
            .where(PostmortemSet.deal_id.in_(deal_ids))
            .order_by(PostmortemRecord.created_at.asc(), PostmortemRecord.id.asc())
        )
    )
    latest_postmortem: dict[str, PostmortemRecord] = {}
    for deal_id, record in postmortem_rows:
        latest_postmortem[deal_id] = record

    rows: list[dict] = []
    for deal in deals:
        screening = latest_screening.get(deal.deal_id)
        explicit = latest_decision.get(deal.deal_id)

        decision = None
        decision_source = None
        decision_rationale = None
        decision_reason_codes: list[str] = []
        decision_at = None

        if explicit is not None:
            decision = _decision_from_record(explicit)
            decision_source = (
                "HUMAN"
                if str(explicit.decided_by_type).upper() == "HUMAN"
                else str(explicit.decided_by_type).upper()
            )
            decision_rationale = explicit.rationale
            decision_reason_codes = _clean_reason_codes(
                (explicit.payload_json or {}).get("reason_codes")
            )
            decision_at = explicit.created_at

        submitted = deal.deal_id in submitted_at
        if decision is None and submitted:
            decision = "GO"
            decision_source = "WORKFLOW"
        if decision is None and str(deal.current_status) in _STATUS_IMPLIED_NO_GO:
            decision = "NO_GO"
            decision_source = "WORKFLOW"
        if decision is None and str(deal.current_status) in _STATUS_IMPLIED_GO:
            decision = "GO"
            decision_source = "WORKFLOW"
        if decision is None:
            decision = _screening_decision(screening)
            if decision:
                decision_source = "AGENT_SCREENING"
                decision_rationale = screening.rationale_text
                decision_reason_codes = _clean_reason_codes(screening.reason_codes_json)
                decision_at = screening.created_at
        if decision is None:
            decision = "UNDECIDED"

        outcome = latest_outcome.get(deal.deal_id)
        postmortem = latest_postmortem.get(deal.deal_id)
        rows.append(
            {
                "deal_id": deal.deal_id,
                "procurement_number": deal.procurement_number,
                "title": deal.title,
                "customer_name": deal.customer_name,
                "procurement_channel": (
                    str(deal.procurement_channel) if deal.procurement_channel else None
                ),
                "current_status": str(deal.current_status),
                "priority_bucket": deal.priority_bucket,
                "decision": decision,
                "decision_source": decision_source,
                "decision_rationale": decision_rationale,
                "decision_reason_codes": decision_reason_codes,
                "decision_at": decision_at,
                "screening_status": str(screening.result_status) if screening else None,
                "screening_score": screening.screening_score if screening else None,
                "screening_rationale": screening.rationale_text if screening else None,
                "screening_reason_codes": (
                    _clean_reason_codes(screening.reason_codes_json) if screening else []
                ),
                "submitted": submitted,
                "submitted_at": submitted_at.get(deal.deal_id),
                "outcome": str(outcome.outcome_code) if outcome else None,
                "outcome_rationale": outcome.rationale if outcome else None,
                "outcome_at": outcome.effective_at if outcome else None,
                "postmortem_root_cause": (
                    postmortem.root_cause_summary if postmortem else None
                ),
                "created_at": deal.created_at,
                "updated_at": deal.updated_at,
            }
        )
    return rows


def _matches_filters(
    row: dict,
    *,
    decision: str | None,
    outcome: str | None,
    submitted: bool | None,
    q: str | None,
) -> bool:
    if decision and row["decision"] != decision.upper():
        return False
    if outcome and (row["outcome"] or "").upper() != outcome.upper():
        return False
    if submitted is not None and row["submitted"] is not submitted:
        return False
    if q:
        needle = q.strip().lower()
        haystack = " ".join(
            str(value or "")
            for value in (
                row["procurement_number"],
                row["title"],
                row["customer_name"],
                row["decision_rationale"],
                row["outcome_rationale"],
            )
        ).lower()
        if needle not in haystack:
            return False
    return True


def build_procurement_portfolio(
    session: Session,
    *,
    decision: str | None = None,
    outcome: str | None = None,
    submitted: bool | None = None,
    q: str | None = None,
) -> dict:
    rows = [
        row
        for row in _portfolio_rows(session)
        if _matches_filters(
            row,
            decision=decision,
            outcome=outcome,
            submitted=submitted,
            q=q,
        )
    ]

    decision_counts = Counter(row["decision"] for row in rows)
    outcome_counts = Counter((row["outcome"] or "").upper() for row in rows)
    submitted_count = sum(1 for row in rows if row["submitted"])

    no_go_reasons: Counter[str] = Counter()
    for row in rows:
        if row["decision"] != "NO_GO":
            continue
        codes = row["decision_reason_codes"] or row["screening_reason_codes"]
        if codes:
            no_go_reasons.update(codes)
        else:
            no_go_reasons["UNCLASSIFIED"] += 1

    decided_outcomes = (
        outcome_counts["WON"] + outcome_counts["LOST"] + outcome_counts["REJECTED"]
    )
    summary = {
        "total_considered": len(rows),
        "go": decision_counts["GO"],
        "no_go": decision_counts["NO_GO"],
        "needs_review": decision_counts["NEEDS_REVIEW"],
        "undecided": decision_counts["UNDECIDED"],
        "submitted": submitted_count,
        "won": outcome_counts["WON"],
        "lost": outcome_counts["LOST"],
        "rejected": outcome_counts["REJECTED"],
        "cancelled": outcome_counts["CANCELLED"],
        "submission_rate": (
            round(submitted_count / decision_counts["GO"], 4)
            if decision_counts["GO"]
            else 0.0
        ),
        "win_rate": (
            round(outcome_counts["WON"] / decided_outcomes, 4)
            if decided_outcomes
            else 0.0
        ),
        "no_go_reason_counts": dict(
            sorted(no_go_reasons.items(), key=lambda item: (-item[1], item[0]))
        ),
    }
    return {"summary": summary, "items": rows}


def create_portfolio_procurement(
    session: Session,
    payload: CreatePortfolioProcurementRequest,
) -> dict:
    intake, _ = create_tender_intake(
        session,
        CreateTenderIntakeRequest(
            source_type=TenderSourceType.PORTAL if payload.source_url else TenderSourceType.MANUAL,
            source_channel="procurement_portfolio",
            source_title=payload.title.strip(),
            source_customer_name=payload.customer_name.strip(),
            source_procurement_number=payload.procurement_number.strip(),
            payload_json={
                "portal_url": payload.source_url.strip() if payload.source_url else None,
                "portfolio_manual_entry": True,
            },
            initial_source_type=InitialSourceType.MANUAL_ENTRY,
            direction_type=payload.direction_type,
            domain_type=payload.domain_type.strip(),
        ),
    )
    portfolio = build_procurement_portfolio(session)
    return next(item for item in portfolio["items"] if item["deal_id"] == intake.deal_id)


def record_portfolio_decision(
    session: Session,
    *,
    deal_id: str,
    payload: RecordPortfolioDecisionRequest,
) -> dict:
    reason_codes = [code.strip() for code in payload.reason_codes if code.strip()]
    append_decision(
        session,
        AppendDecisionRequest(
            deal_id=deal_id,
            decision_code="PORTFOLIO_BID_DECISION",
            decided_by_type=DecisionByType.HUMAN,
            decided_by_ref=payload.decided_by_ref,
            rationale=payload.rationale.strip(),
            payload_json={
                "decision": payload.decision,
                "reason_codes": reason_codes,
                "source": "procurement_portfolio",
            },
        ),
    )
    portfolio = build_procurement_portfolio(session)
    return next(item for item in portfolio["items"] if item["deal_id"] == deal_id)
