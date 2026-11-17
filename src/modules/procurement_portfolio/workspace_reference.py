"""Restricted Workspace internal procurement read model (WSF-07B).

Product-owned projection only. No HTTP route, credentials, independent ownership
proof or live access granted by construction of this scope object.
A server-side admitted source capability must supply authorize and a verified
read-only session. No generic listing and no title/rationale/payload export.
"""
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord, EventRecord
from src.modules.outcome_intake.models import (
    OutcomeIntakeBinding,
    OutcomeIntakeRecord,
    OutcomeIntakeSet,
)
from src.modules.tender_screening.models import TenderScreeningRecord
from src.shared.enums import DealStatus

from .service import _EXPLICIT_DECISION_CODES

SCHEMA = "arvectum.tender.internal-procurement-reference/1"
MAX_DEALS = 21
BID_VALUES = {"GO", "NO_GO", "NEEDS_REVIEW", "DEFER", "GO_WITH_CONDITIONS"}
CODE_VALUES = {
    "APPROVE_TO_BID": "GO",
    "DECLINE_TO_BID": "NO_GO",
    "DEAL_MARKED_REJECTED_EARLY": "NO_GO",
    "OPERATOR_REJECTED_PREBID": "NO_GO",
    "OPERATOR_MARKED_NEEDS_MORE_REVIEW": "NEEDS_REVIEW",
}


class ReferenceDenied(ValueError):
    pass


def _ref(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ReferenceDenied("invalid reference")
    return value


def _stamp(value):
    if not isinstance(value, datetime):
        raise ReferenceDenied("invalid timestamp")
    # Product UTC DateTime columns; SQLite tests decode naive UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ReferenceDenied("UTC required")
    return value


@dataclass(frozen=True)
class ReferenceScope:
    binding_id: str
    source_release: str
    database_binding: str
    deal_ids: frozenset[str]
    starts_at: datetime
    expires_at: datetime


def _check(expected, authorize, now):
    if not isinstance(expected, ReferenceScope) or authorize() != expected:
        raise ReferenceDenied("source admission missing or changed")
    _ref(expected.binding_id)
    _ref(expected.database_binding)
    if not isinstance(expected.source_release, str) or not re.fullmatch(r"[a-f0-9]{40}", expected.source_release):
        raise ReferenceDenied("release pin required")
    start, end = _utc(expected.starts_at), _utc(expected.expires_at)
    if not start <= _utc(now) < end or end - start > timedelta(days=30):
        raise ReferenceDenied("binding expired")
    if not isinstance(expected.deal_ids, frozenset) or not 1 <= len(expected.deal_ids) <= MAX_DEALS:
        raise ReferenceDenied("fixed deal scope required")
    for deal in expected.deal_ids:
        _ref(deal)


def _one_or_unknown(session, statement, time_field):
    # A tie at the latest timestamp is not a reliable ordering of decisions.
    rows = list(session.execute(statement.limit(2)))
    if not rows:
        return None
    if len(rows) == 2 and rows[0]._mapping[time_field] == rows[1]._mapping[time_field]:
        return None
    return rows[0]._mapping


def _decision(session, deal_id):
    r = DecisionRecord
    row = _one_or_unknown(session, select(
        r.decision_id, r.decision_code, r.decided_by_type,
        (func.length(func.trim(func.coalesce(r.decided_by_ref, ""))) > 0).label("actor_known"),
        r.payload_json["decision"].as_string().label("value"), r.created_at,
    ).where(r.deal_id == deal_id, r.decision_code.in_(sorted(_EXPLICIT_DECISION_CODES)))
        .order_by(r.created_at.desc(), r.id.desc()), "created_at")
    if row is None:
        return None
    value = CODE_VALUES.get(row["decision_code"], row["value"])
    actor = row["decided_by_type"]
    if actor not in ("HUMAN", "AGENT", "SYSTEM", "MODULE"):
        actor = "UNKNOWN"
    return {
        "ref": _ref(row["decision_id"]),
        "code": row["decision_code"],
        "value": value if value in BID_VALUES else "UNKNOWN",
        "actor_type": actor,
        "actor_reference_present": bool(row["actor_known"]),
        "at": _stamp(row["created_at"]),
        "owner_approval_verified": False,
    }


def _screening(session, deal_id):
    r = TenderScreeningRecord
    row = _one_or_unknown(session, select(r.screening_id, r.result_status, r.created_at).where(
        r.deal_id == deal_id).order_by(r.created_at.desc(), r.id.desc()), "created_at")
    if row is None:
        return None
    return {
        "ref": _ref(row["screening_id"]),
        "source": "AGENT_SCREENING",
        "value": {"PASS": "GO", "FAIL": "NO_GO", "NEEDS_REVIEW": "NEEDS_REVIEW"}.get(row["result_status"], "UNKNOWN"),
        "at": _stamp(row["created_at"]),
    }


def _submission(session, deal_id):
    r = EventRecord
    row = _one_or_unknown(session, select(r.event_id, r.created_at).where(
        r.deal_id == deal_id, r.event_code == "submission_execution_submitted")
        .order_by(r.created_at.desc(), r.id.desc()), "created_at")
    if row is None:
        return None
    return {"ref": _ref(row["event_id"]), "source": "RECORDED_SUBMISSION_EVENT",
            "at": _stamp(row["created_at"]), "external_submission_verified": False}


def _outcome(session, deal_id):
    r, s, b = OutcomeIntakeRecord, OutcomeIntakeSet, OutcomeIntakeBinding
    row = _one_or_unknown(session, select(
        r.outcome_intake_id, r.outcome_code, r.effective_at,
    ).join(s, s.outcome_intake_set_id == r.outcome_intake_set_id)
        .where(s.deal_id == deal_id).order_by(r.effective_at.desc(), r.id.desc()), "effective_at")
    if row is None:
        return None
    binding = session.execute(select(b.artifact_ref).where(
        b.outcome_intake_id == row["outcome_intake_id"]).order_by(b.artifact_ref).limit(1)).first()
    return {
        "ref": _ref(row["outcome_intake_id"]),
        "code": row["outcome_code"] if row["outcome_code"] in ("WON", "LOST", "REJECTED", "CANCELLED") else "UNKNOWN",
        "at": _stamp(row["effective_at"]),
        "artifact_ref": _ref(binding[0]) if binding is not None else None,
        "external_outcome_verified": False,
    }


def read_internal_procurement(session: Session, *, scope, authorize, clock):
    """Read fixed admitted identities, no domain state transitions or inferred GO.

    authorize must prove current independent source permission and actual database/
    release binding, not merely echo browser input. Caller must supply a read-only
    consistent DB transaction. This function doesn't provision those prerequisites.
    """
    _check(scope, authorize, clock())
    if session.new or session.dirty or session.deleted:
        raise ReferenceDenied("read-only session required")
    d = Deal
    with session.no_autoflush:
        records = list(session.execute(select(
            d.deal_id, d.procurement_number, d.current_status, d.updated_at,
        ).where(d.is_deleted.is_(False), d.deal_id.in_(sorted(scope.deal_ids)))
            .order_by(d.deal_id).limit(MAX_DEALS + 1)))
        if {r.deal_id for r in records} != scope.deal_ids or len(records) != len(scope.deal_ids):
            raise ReferenceDenied("admitted deal missing or changed")
        items = []
        for row in records:
            number = row.procurement_number
            if number is not None and not re.fullmatch(r"[0-9]{11}|[0-9]{19}", number):
                number = None
            items.append({
                "deal_id": _ref(row.deal_id),
                "procurement_number": number,
                "workflow_status": row.current_status if row.current_status in {v.value for v in DealStatus} else "UNKNOWN",
                "updated_at": _stamp(row.updated_at),
                "recorded_decision": _decision(session, row.deal_id),
                "recommendation": _screening(session, row.deal_id),
                "submission": _submission(session, row.deal_id),
                "outcome": _outcome(session, row.deal_id),
                "current_legal_status": "unknown",
            })
        observed = clock()
        _check(scope, authorize, observed)
    return {"schema": SCHEMA, "binding_id": scope.binding_id,
            "source_release": scope.source_release, "database_binding": scope.database_binding,
            "observed_at": _stamp(observed),
            "coverage": "admitted-identity-set-only", "items": items,
            "canonical_authority": False}
