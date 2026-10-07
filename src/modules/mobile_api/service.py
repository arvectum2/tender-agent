from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.event_log.models import DecisionRecord
from src.modules.event_log.schemas import AppendDecisionRequest
from src.modules.event_log.service import append_decision
from src.modules.procurement_portfolio.service import build_procurement_portfolio
from src.modules.tender_intake.models import TenderIntakeRecord, TenderSourcePayload
from src.shared.enums import DecisionByType
from src.shared.errors import NotFoundError

from .models import MobileDeviceAccess, MobileDeviceRegistration
from .push import normalize_apns_token
from .schemas import MobileDecisionRequest, MobileDeviceRegistrationRequest


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



def _latest_daily_tender_items(
    session: Session,
    deal_ids: list[str],
) -> dict[str, DailyTenderRunItem]:
    if not deal_ids:
        return {}
    rows = list(
        session.scalars(
            select(DailyTenderRunItem)
            .join(DailyTenderRun, DailyTenderRun.run_id == DailyTenderRunItem.run_id)
            .where(
                DailyTenderRunItem.deal_id.in_(deal_ids),
                DailyTenderRunItem.status == "MANAGER_READY",
            )
            .order_by(
                DailyTenderRun.created_at.asc(),
                DailyTenderRunItem.updated_at.asc(),
                DailyTenderRunItem.id.asc(),
            )
        )
    )
    return {row.deal_id: row for row in rows if row.deal_id}


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
    daily_items = _latest_daily_tender_items(session, deal_ids)

    items = []
    for row in rows:
        daily_item = daily_items.get(row["deal_id"])
        recommendation, recommendation_rationale, recommendation_codes = _recommendation(row)
        if daily_item is not None and daily_item.agent_recommendation in {"GO", "NO_GO", "NEEDS_REVIEW"}:
            recommendation = daily_item.agent_recommendation
            recommendation_rationale = daily_item.agent_rationale
            recommendation_codes = ["DAILY_TENDER_RUN"]
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
                "source_url": (
                    daily_item.source_url if daily_item is not None and daily_item.source_url
                    else urls.get(row["deal_id"])
                ),
                "nmck_rub": daily_item.nmck_amount if daily_item is not None else None,
                "deadline_at": daily_item.deadline_at if daily_item is not None else None,
                "recommendation": recommendation,
                "recommendation_rationale": recommendation_rationale,
                "recommendation_reason_codes": recommendation_codes,
                "recommendation_confidence": (
                    daily_item.agent_confidence if daily_item is not None else None
                ),
                "recommendation_reasons": (
                    list(daily_item.strongest_reasons_json or [])
                    if daily_item is not None
                    else []
                ),
                "recommendation_blockers": (
                    list(daily_item.blockers_json or [])
                    if daily_item is not None
                    else []
                ),
                "recommendation_unknowns": (
                    list(daily_item.unknowns_json or [])
                    if daily_item is not None
                    else []
                ),
                "analysis_run_id": daily_item.analysis_run_id if daily_item is not None else None,
                "analysis_report_path": (
                    daily_item.analysis_report_path if daily_item is not None else None
                ),
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



def build_mobile_digest(session: Session) -> dict:
    run = session.scalar(
        select(DailyTenderRun)
        .order_by(DailyTenderRun.created_at.desc(), DailyTenderRun.id.desc())
        .limit(1)
    )
    if run is None or not isinstance(run.digest_json, dict):
        return {
            "run_id": None,
            "profile_id": None,
            "profile_version": None,
            "counts": {},
            "actionable": [],
            "human_control": {
                "decision_required": True,
                "allowed_actions": ["GO", "NO_GO", "DEFER"],
                "external_submission_allowed": False,
            },
        }

    digest = dict(run.digest_json)
    portfolio = build_mobile_portfolio(session)
    current_by_deal = {item["deal_id"]: item for item in portfolio["items"]}
    actionable: list[dict] = []
    for snapshot in digest.get("actionable", []):
        if not isinstance(snapshot, dict):
            continue
        deal_id = snapshot.get("deal_id")
        current = current_by_deal.get(deal_id)
        if current is None or not current["needs_attention"]:
            continue
        merged = dict(snapshot)
        merged.update(
            {
                "human_decision": current["human_decision"],
                "human_rationale": current["human_rationale"],
                "human_reason_codes": current["human_reason_codes"],
                "deferred_until": (
                    current["deferred_until"].isoformat()
                    if current["deferred_until"] is not None
                    else None
                ),
                "needs_attention": current["needs_attention"],
            }
        )
        actionable.append(merged)

    counts = dict(digest.get("counts") or {})
    counts["needs_manager"] = len(actionable)
    digest["counts"] = counts
    digest["actionable"] = actionable
    return digest

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


def record_mobile_decision(
    session: Session,
    deal_id: str,
    payload: MobileDecisionRequest,
    *,
    actor_ref: str,
) -> dict:
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
            decided_by_ref=actor_ref,
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

def activate_mobile_device_access(
    session: Session,
    *,
    device_id: str,
    device_name: str | None,
) -> MobileDeviceAccess:
    access = session.scalar(
        select(MobileDeviceAccess).where(MobileDeviceAccess.device_id == device_id)
    )
    now = datetime.now(UTC)
    if access is None:
        access = MobileDeviceAccess(
            device_id=device_id,
            device_name=device_name,
            is_revoked=False,
            paired_at=now,
            revoked_at=None,
            updated_at=now,
        )
    else:
        access.device_name = device_name
        access.is_revoked = False
        access.paired_at = now
        access.revoked_at = None
        access.updated_at = now
    session.add(access)
    session.commit()
    session.refresh(access)
    return access


def register_mobile_device(
    session: Session,
    *,
    device_id: str,
    payload: MobileDeviceRegistrationRequest,
) -> dict:
    token = normalize_apns_token(payload.apns_token)
    registration = session.scalar(
        select(MobileDeviceRegistration).where(
            MobileDeviceRegistration.device_id == device_id
        )
    )
    now = datetime.now(UTC)
    if registration is None:
        registration = MobileDeviceRegistration(
            device_id=device_id,
            device_name=payload.device_name,
            apns_token=token,
            apns_environment=payload.environment,
            app_version=payload.app_version,
            is_enabled=True,
            registered_at=now,
            updated_at=now,
        )
    else:
        registration.device_name = payload.device_name
        registration.apns_token = token
        registration.apns_environment = payload.environment
        registration.app_version = payload.app_version
        registration.is_enabled = True
        registration.updated_at = now
    session.add(registration)
    session.commit()
    session.refresh(registration)
    return {
        "device_id": registration.device_id,
        "environment": registration.apns_environment,
        "device_name": registration.device_name,
        "app_version": registration.app_version,
        "enabled": registration.is_enabled,
        "registered_at": registration.registered_at,
        "updated_at": registration.updated_at,
    }


def revoke_mobile_device(session: Session, *, device_id: str) -> bool:
    now = datetime.now(UTC)
    registration = session.scalar(
        select(MobileDeviceRegistration).where(
            MobileDeviceRegistration.device_id == device_id
        )
    )
    if registration is not None:
        registration.is_enabled = False
        registration.apns_token = ""
        registration.updated_at = now
        session.add(registration)

    access = session.scalar(
        select(MobileDeviceAccess).where(MobileDeviceAccess.device_id == device_id)
    )
    if access is None:
        access = MobileDeviceAccess(
            device_id=device_id,
            device_name=None,
            is_revoked=True,
            paired_at=now,
            revoked_at=now,
            updated_at=now,
        )
    else:
        access.is_revoked = True
        access.revoked_at = now
        access.updated_at = now
    session.add(access)
    session.commit()
    return True
