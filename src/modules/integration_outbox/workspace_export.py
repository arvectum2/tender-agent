"""Read-only Workspace export candidate, not registered as a production route.

Exact tenant/member/token and project binding must be admitted independently.
No generic outbox listing, event acknowledgement, or transport.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import IntegrationOutboxEvent
from .service import stable_event_key

SCHEMA = "arvectum.tender.workspace-event-window/1"
MAX_ROWS = 100
KINDS = {"analysis_completed": "analysis_run", "review_required": "procurement_case"}


class ExportDenied(ValueError):
    pass


def _opaque(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ExportDenied("invalid event reference")
    return value


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ExportDenied("UTC boundary required")
    return value.astimezone(timezone.utc)


def _stored_time(value):
    # Model's DateTime(timezone=True) is UTC; SQLite fixtures return naive UTC.
    if not isinstance(value, datetime):
        raise ExportDenied("invalid stored timestamp")
    return _utc(value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc))


@dataclass(frozen=True)
class ExportScope:
    tenant_id: str
    customer_id: str
    member_id: str
    token_id: str
    project_ids: frozenset[str]
    starts_at: datetime
    expires_at: datetime


def check_scope(scope, principal, now):
    if not isinstance(scope, ExportScope):
        raise ExportDenied("export not admitted")
    for name in ("tenant_id", "customer_id", "member_id", "token_id"):
        if _opaque(getattr(scope, name)) != getattr(principal, name, None):
            raise ExportDenied("export scope mismatch")
    if getattr(principal, "role", None) != "owner":
        raise ExportDenied("owner role required")
    start, end, current = map(_utc, (scope.starts_at, scope.expires_at, now))
    if not start <= current < end or end-start > timedelta(days=30):
        raise ExportDenied("export window expired")
    if not isinstance(scope.project_ids, frozenset) or not 1 <= len(scope.project_ids) <= 32:
        raise ExportDenied("exact project scope required")
    for p in scope.project_ids:
        _opaque(p)


def _row(event, scope, now):
    e=event.envelope
    keys={"schema_version","event_key","event_type","tenant_id","aggregate_type","aggregate_id","occurred_at","data"}
    if not isinstance(e,dict) or set(e)!=keys or e["schema_version"]!="integration-event-v1":
        raise ExportDenied("event schema mismatch")
    kind=event.event_type
    if kind not in KINDS or event.aggregate_type!=KINDS[kind] or event.tenant_id!=scope.customer_id:
        raise ExportDenied("event scope mismatch")
    for k in ("event_key","event_type","tenant_id","aggregate_type","aggregate_id"):
        if e[k]!=getattr(event,k):raise ExportDenied("event envelope mismatch")
    d=e["data"]
    needed={"project_id","case_id","status"} if kind=="analysis_completed" else {"project_id","run_id","reason"}
    if not isinstance(d,dict) or set(d)!=needed or d["project_id"] not in scope.project_ids:
        raise ExportDenied("event project or payload mismatch")
    aggregate=_opaque(event.aggregate_id)
    _opaque(d["project_id"])
    if kind=="analysis_completed":
        _opaque(d["case_id"]); run=aggregate
        if d["status"]!="completed":raise ExportDenied("event result mismatch")
    else:
        run=_opaque(d["run_id"])
        if d["reason"]!="analysis_completed_operator_review":raise ExportDenied("event reason mismatch")
    if stable_event_key(kind,event.aggregate_type,aggregate,run)!=event.event_key:
        raise ExportDenied("event identity mismatch")
    try:occurred=_utc(datetime.fromisoformat(e["occurred_at"].replace("Z","+00:00")))
    except (TypeError,ValueError,AttributeError) as exc:raise ExportDenied("invalid occurrence") from exc
    created=_stored_time(event.created_at)
    if not occurred<=created<=now:raise ExportDenied("event time conflict")
    # Strict allowlist, no arbitrary payload or ORM serialization.
    return {"id":_opaque(event.id),"event_key":event.event_key,"event_type":kind,
            "tenant_id":scope.customer_id,"aggregate_type":event.aggregate_type,"aggregate_id":aggregate,
            "envelope":{**{k:e[k] for k in keys if k!="data"},"data":dict(d)},
            "created_at":created.isoformat()}


def project_event_window(session: Session, *, scope, authorize, since, until, now):
    """Observe a bounded half-open time window, or return overflow with no rows.

    authorize must revalidate the actual server-side principal and legal grant.
    Inactive source, malformed data or foreign scope denies the entire result.
    A window is not an exhaustive commit-log cursor; late commits require
    overlapping rescans. No writes, flushes, commits, delivery or acknowledgement.
    """
    current=_utc(now);left,right=_utc(since),_utc(until)
    if not left<right<=current or right-left>timedelta(hours=24):
        raise ExportDenied("bounded observation window required")
    check_scope(scope,authorize(),current)
    if session.new or session.dirty or session.deleted:
        raise ExportDenied("read-only session required")
    row=IntegrationOutboxEvent
    with session.no_autoflush:
        candidates=list(session.scalars(select(row).where(
            row.tenant_id==scope.customer_id,
            or_(*(and_(row.event_type==kind,row.aggregate_type==aggregate) for kind,aggregate in KINDS.items())),
            row.envelope["data"]["project_id"].as_string().in_(sorted(scope.project_ids)),
            row.created_at>=left,row.created_at<right,
        ).order_by(row.created_at,row.id).limit(MAX_ROWS+1)))
        check_scope(scope,authorize(),current)
        if len(candidates)>MAX_ROWS:
            return {"schema":SCHEMA,"state":"overflow","since":left.isoformat(),"until":right.isoformat(),
                    "coverage":"partial","rows":[]}
        rows=[_row(e,scope,current) for e in candidates]
        check_scope(scope,authorize(),current)
    return {"schema":SCHEMA,"state":"observed","since":left.isoformat(),"until":right.isoformat(),
            "coverage":"partial","rows":rows}
