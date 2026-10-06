from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.event_log.models import DecisionRecord
from src.modules.event_log.schemas import AppendDecisionRequest
from src.modules.event_log.service import append_decision
from src.modules.procurement_portfolio.service import build_procurement_portfolio
from src.modules.tender_intake.models import TenderIntakeRecord, TenderSourcePayload
from src.shared.enums import DecisionByType
from src.shared.errors import NotFoundError

from .schemas import MobileDecisionRequest


def _latest_mobile_decisions(session: Session, deal_ids: list[str]) -> dict[str, DecisionRecord]:
    if not deal_ids:
        return {}
    rows = list(
        session.scalars(
            select(DecisionRecord)
            .where(
                DecisionRecord.deal_id.in_(deal_ids),
                DecisionRecord.decision_code == "PORTFOLIO_BID_DECISION",
            )
            .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc())
        )
    )
    return {row.deal_id: row for row in rows}


def _source_urls(session: Session, deal_ids: list[str]) -> dict[str, str]:
    if not deal_ids:
        return {}
    rows = list(
        session.execute(
            select(TenderIntakeRecord.deal_id, TenderSourcePayload.payload_json)
            .join(TenderSourcePayload, TenderSourcePayload.intake_id == TenderIntakeRecord.intake_id)
            .where(TenderIntakeRecord.deal_id.in_(deal_ids))
            .order_by(TenderSourcePayload.created_at.asc(), TenderSourcePayload.id.asc())
        )
    )
    result: dict[str, str] = {}
    for deal_id, payload in rows:
        if not isinstance(payload, dict):
            continue
        value = payload.get("portal_url") or payload.get("source_url") or payload.get("url")
        if isinstance(value, str) and value.strip():
            result[deal_id] = value.strip()
    return result


def _human_state(record: DecisionRecord | None, fallback: dict) -> tuple[str, str | None, list[str], datetime | None]:
    if record is None or str(record.decided_by_type).upper() != "HUMAN":
        return "PENDING", None, [], None
    payload = record.payload_json or {}
    action = str(payload.get("mobile_action") or payload.get("decision") or "").upper()
    if action == "DEFER":
        raw = payload.get("deferred_until")
        deferred_until = datetime.fromisoformat(raw) if isinstance(raw, str) else None
        return "DEFER", record.rationale, _clean_codes(payload.get("reason_codes")), deferred_until
    if action in {"GO", "GO_WITH_CONDITIONS"}:
        return "GO", record.rationale, _clean_codes(payload.get("reason_codes")), None
    if action == "NO_GO":
        return "NO_GO", record.rationale, _clean_codes(payload.get("reason_codes")), None
    if fallback["decision"] == "GO":
        return "GO", record.rationale, _clean_codes(payload.get("reason_codes")), None
    if fallback["decision"] == "NO_GO":
        return "NO_GO", record.rationale, _clean_codes(payload.get("reason_codes")), None
    return "PENDING", record.rationale, _clean_codes(payload.get("reason_codes")), None


def _clean_codes(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _recommendation(row: dict) -> tuple[str, str | None, list[str]]:
    status = str(row.get("screening_status") or "").upper()
    if status == "PASS":
        return "GO", row.get("screening_rationale"), row.get("screening_reason_codes") or []
    if status == "FAIL":
        return "NO_GO", row.get("screening_rationale"), row.get("screening_reason_codes") or []
    if status == "NEEDS_REVIEW":
        return "NEEDS_REVIEW", row.get("screening_rationale"), row.get("screening_reason_codes") or []

    decision = str(row.get("decision") or "UNDECIDED").upper()
    if decision in {"GO", "NO_GO", "NEEDS_REVIEW"}:
        return decision, row.get("decision_rationale"), row.get("decision_reason_codes") or []
    return "UNDECIDED", None, []


def _is_attention_due(human_decision: str, deferred_until: datetime | None) -> bool:
    if human_decision == "PENDING":
        return True
    if human_decision != "DEFER":
        return False
    if deferred_until is None:
        return True
    now = datetime.now(UTC)
    candidate = deferred_until
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=UTC)
    return candidate <= now


def build_mobile_portfolio(session: Session) -> dict:
    portfolio = build_procurement_portfolio(session)
    rows = portfolio["items"]
    deal_ids = [row["deal_id"] for row in rows]
    mobile_decisions = _latest_mobile_decisions(session, deal_ids)
    urls = _source_urls(session, deal_ids)

    items = []
    for row in rows:
        recommendation, recommendation_rationale, recommendation_codes = _recommendation(row)
        human_decision, human_rationale, human_codes, deferred_until = _human_state(
            mobile_decisions.get(row["deal_id"]),
            row,
        )
        items.append(
            {
                "deal_id": row["deal_id"],
                "procurement_number": row["procurement_number"],
                "title": row["title"],
                "customer_name": row["customer_name"],
                "source_url": urls.get(row["deal_id"]),
                "nmck_rub": None,
                "deadline_at": None,
                "recommendation": recommendation,
                "recommendation_rationale": recommendation_rationale,
                "recommendation_reason_codes": recommendation_codes,
                "human_decision": human_decision,
                "human_rationale": human_rationale,
                "human_reason_codes": human_codes,
                "deferred_until": deferred_until,
                "needs_attention": _is_attention_due(human_decision, deferred_until),
                "submitted": row["submitted"],
                "submitted_at": row["submitted_at"],
                "outcome": row["outcome"],
                "outcome_rationale": row["outcome_rationale"],
                "outcome_at": row["outcome_at"],
                "postmortem_root_cause": row["postmortem_root_cause"],
                "current_status": row["current_status"],
                "updated_at": row["updated_at"],
            }
        )
    return {"summary": portfolio["summary"], "items": items}


def build_mobile_inbox(session: Session) -> dict:
    portfolio = build_mobile_portfolio(session)
    items = [item for item in portfolio["items"] if item["needs_attention"]]
    deferred_count = sum(1 for item in portfolio["items"] if item["human_decision"] == "DEFER")
    summary = portfolio["summary"]
    return {
        "summary": {
            "total_portfolio": summary["total_considered"],
            "needs_attention": len(items),
            "deferred": deferred_count,
            "submitted": summary["submitted"],
            "won": summary["won"],
            "lost": summary["lost"],
            "cancelled": summary["cancelled"],
        },
        "items": items,
    }


def get_mobile_procurement(session: Session, deal_id: str) -> dict:
    portfolio = build_mobile_portfolio(session)
    for item in portfolio["items"]:
        if item["deal_id"] == deal_id:
            return item
    raise NotFoundError(f"Deal '{deal_id}' was not found")


def _existing_idempotent_decision(
    session: Session,
    *,
    deal_id: str,
    idempotency_key: str,
) -> DecisionRecord | None:
    rows = list(
        session.scalars(
            select(DecisionRecord)
            .where(
                DecisionRecord.deal_id == deal_id,
                DecisionRecord.decision_code == "PORTFOLIO_BID_DECISION",
            )
            .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
        )
    )
    for row in rows:
        payload = row.payload_json or {}
        if payload.get("idempotency_key") == idempotency_key:
            return row
    return None


def record_mobile_decision(session: Session, deal_id: str, payload: MobileDecisionRequest) -> dict:
    if _existing_idempotent_decision(
        session,
        deal_id=deal_id,
        idempotency_key=payload.idempotency_key,
    ):
        return get_mobile_procurement(session, deal_id)

    reason_codes = [code.strip() for code in payload.reason_codes if code.strip()]
    rationale = (payload.rationale or "").strip() or f"{payload.action} recorded from Tender Agent iOS."

    if payload.action == "DEFER":
        decision = "NEEDS_REVIEW"
        mobile_action = "DEFER"
        deferred_until = payload.deferred_until.isoformat() if payload.deferred_until else None
    else:
        decision = payload.action
        mobile_action = payload.action
        deferred_until = None

    append_decision(
        session,
        AppendDecisionRequest(
            deal_id=deal_id,
            decision_code="PORTFOLIO_BID_DECISION",
            decided_by_type=DecisionByType.HUMAN,
            decided_by_ref=payload.actor_ref,
            rationale=rationale,
            payload_json={
                "decision": decision,
                "mobile_action": mobile_action,
                "deferred_until": deferred_until,
                "reason_codes": reason_codes,
                "source": "tender_agent_ios",
                "idempotency_key": payload.idempotency_key,
            },
        ),
    )
    return get_mobile_procurement(session, deal_id)
