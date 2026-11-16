"""Canonical company-owned cases; saved EIS references are not verified facts."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from src.modules.customer_pilot.models import (
    PilotAuditEvent,
    PilotProject,
    ProcurementCase,
)
from src.modules.customer_pilot.procurement_import import import_procurement_case
from src.modules.saas_foundation.commercial_sources import commercial_identity
from src.modules.saas_foundation.models import CompanyPortfolioDecision, SaasTenant
from src.modules.saas_foundation.service import (
    TenantPrincipal,
    audit,
    legal_required,
    now_utc,
    role_required,
)

_PROJECT_SLUG = "daily-tender-company-portfolio-v1"
_COMMERCIAL_SLUGS = {p: _PROJECT_SLUG + "-" + p for p in ("workspace", "b2bcenter")}
_PROJECT_SLUGS = (_PROJECT_SLUG, *_COMMERCIAL_SLUGS.values())


class SaveCompanyCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry_number: str = Field(pattern=r"^[0-9]{19,20}$")


class SaveCommercialCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: str = Field(min_length=20, max_length=650)


class CompanyDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["GO", "NO_GO", "DEFER"]
    rationale: str = Field(min_length=1, max_length=2000)
    deferred_until: datetime | None = None
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_action(self):
        self.rationale = self.rationale.strip()
        if not self.rationale:
            raise ValueError("rationale is required")
        if (self.action == "DEFER") != (self.deferred_until is not None):
            raise ValueError("deferred_until is required only for DEFER")
        if self.deferred_until is not None:
            if self.deferred_until.utcoffset() is None:
                raise ValueError("deferred_until must include timezone")
            self.deferred_until = self.deferred_until.astimezone(UTC)
        return self


class CompanyDecisionView(BaseModel):
    decision_id: str
    revision: int
    action: Literal["GO", "NO_GO", "DEFER"]
    rationale: str
    deferred_until: datetime | None
    decided_at: datetime
    decided_by_member_id: str


class CompanyCaseView(BaseModel):
    case_id: str
    registry_number: str | None
    source_kind: Literal["eis_registry_reference", "commercial_reference"]
    source_platform: str = "eis"
    external_id: str | None = None
    source_url: str | None = None
    source_verified: Literal[False]
    revision: int
    decision: CompanyDecisionView | None
    external_submission_allowed: Literal[False]


class CompanyPortfolioPage(BaseModel):
    customer_id: str
    items: list[CompanyCaseView]
    has_more: bool
    external_submission_allowed: Literal[False]


class CompanyDecisionPage(BaseModel):
    items: list[CompanyDecisionView]
    has_more: bool


def _utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _project(session: Session, principal: TenantPrincipal, *, create: bool = False, slug: str = _PROJECT_SLUG):
    if create:
        tenant = session.scalar(select(SaasTenant).where(
            SaasTenant.tenant_id == principal.tenant_id,
            SaasTenant.customer_id == principal.customer_id,
        ).with_for_update())
        if tenant is None:
            raise HTTPException(404, "Company portfolio not found")
    project = session.scalar(select(PilotProject).where(
        PilotProject.customer_id == principal.customer_id,
        PilotProject.internal_slug == slug))
    if project is None and create:
        project = PilotProject(customer_id=principal.customer_id, name="Daily Tender Run", internal_slug=slug)
        session.add(project)
        session.flush()
    return project


def _owned_case(session: Session, principal: TenantPrincipal, case_id: str, *, lock: bool = False):
    query = select(ProcurementCase).join(PilotProject, PilotProject.id == ProcurementCase.project_id).where(
        ProcurementCase.id == case_id,
        ProcurementCase.customer_id == principal.customer_id,
        PilotProject.customer_id == principal.customer_id,
        PilotProject.internal_slug.in_(_PROJECT_SLUGS),
    )
    if lock:
        query = query.with_for_update(of=ProcurementCase)
    case = session.scalar(query)
    if case is None:
        raise HTTPException(404, "Company portfolio case not found")
    return case


def _decision_query(principal: TenantPrincipal, case_id: str):
    return select(CompanyPortfolioDecision).where(
        CompanyPortfolioDecision.case_id == case_id,
        CompanyPortfolioDecision.tenant_id == principal.tenant_id,
    )


def _latest(session: Session, principal: TenantPrincipal, case_id: str):
    return session.scalar(_decision_query(principal, case_id).order_by(CompanyPortfolioDecision.revision.desc()).limit(1))


def _decision_view(row: CompanyPortfolioDecision) -> dict:
    return {"decision_id": row.id, "revision": row.revision, "action": row.action,
            "rationale": row.rationale, "deferred_until": _utc(row.deferred_until),
            "decided_at": _utc(row.created_at), "decided_by_member_id": row.member_id}


def _view(session: Session, principal: TenantPrincipal, case: ProcurementCase) -> dict:
    return _case_view(session, principal, case, _latest(session, principal, case.id))


def _case_view(session, principal, case, latest):
    project = session.get(PilotProject, case.project_id)
    platform = next((p for p, slug in _COMMERCIAL_SLUGS.items() if slug == project.internal_slug), "eis")
    source_url = None
    if platform != "eis":
        event = session.scalar(select(PilotAuditEvent).where(PilotAuditEvent.customer_id == principal.customer_id, PilotAuditEvent.project_id == case.project_id, PilotAuditEvent.procurement_case_id == case.id, PilotAuditEvent.event_type == "commercial_reference_saved").order_by(PilotAuditEvent.created_at, PilotAuditEvent.id).limit(1))
        if event:
            candidate = event.payload.get("source_url")
            try:
                if commercial_identity(candidate) == (platform, case.procurement_number):
                    source_url = candidate
            except ValueError:
                pass
    return {"case_id": case.id, "registry_number": case.procurement_number if platform == "eis" else None,
            "source_kind": "eis_registry_reference" if platform == "eis" else "commercial_reference",
            "source_platform": platform, "external_id": case.procurement_number, "source_url": source_url, "source_verified": False,
            "revision": latest.revision if latest else 0,
            "decision": _decision_view(latest) if latest else None,
            "external_submission_allowed": False}


def save_case(session: Session, principal: TenantPrincipal, payload: SaveCompanyCase) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    project = _project(session, principal, create=True)
    imported = import_procurement_case(session, customer_id=principal.customer_id,
                                       project_id=project.id, raw_input=payload.registry_number, surface="manual")
    return _view(session, principal, _owned_case(session, principal, imported["id"]))


def save_commercial_case(session: Session, principal: TenantPrincipal, payload: SaveCommercialCase) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    try:
        platform, external_id = commercial_identity(payload.source_url)
    except ValueError as exc:
        raise HTTPException(422, "Unsupported exact public commercial card URL") from exc
    project = _project(session, principal, create=True, slug=_COMMERCIAL_SLUGS[platform])
    case = session.scalar(select(ProcurementCase).where(ProcurementCase.customer_id == principal.customer_id,
        ProcurementCase.project_id == project.id, ProcurementCase.procurement_number == external_id))
    if case is None:
        case = ProcurementCase(customer_id=principal.customer_id, project_id=project.id,
                               procurement_number=external_id, artifact_key=f"c_{uuid4().hex}")
        session.add(case)
        session.flush()
        session.add(PilotAuditEvent(customer_id=principal.customer_id, project_id=project.id, procurement_case_id=case.id, event_type="commercial_reference_saved", payload={"source_url": payload.source_url, "source_platform": platform, "external_id": external_id}))
        audit(session, principal.tenant_id, "company_commercial_reference_saved", principal.member_id, detail=f"{case.id}:{platform}:{external_id}")
    session.commit()
    return _view(session, principal, case)


def list_cases(session: Session, principal: TenantPrincipal, *, offset: int, limit: int) -> dict:
    legal_required(session, principal)
    cases = list(session.scalars(select(ProcurementCase).join(PilotProject, PilotProject.id == ProcurementCase.project_id).where(
        ProcurementCase.customer_id == principal.customer_id, PilotProject.customer_id == principal.customer_id,
        PilotProject.internal_slug.in_(_PROJECT_SLUGS),
    ).order_by(ProcurementCase.created_at.desc(), ProcurementCase.id.desc()).offset(offset).limit(limit + 1)))
    return {"customer_id": principal.customer_id, "items": [_view(session, principal, c) for c in cases[:limit]],
            "has_more": len(cases) > limit, "external_submission_allowed": False}


def get_case(session: Session, principal: TenantPrincipal, case_id: str) -> dict:
    legal_required(session, principal)
    return _view(session, principal, _owned_case(session, principal, case_id))


def decision_history(session: Session, principal: TenantPrincipal, case_id: str, *, offset: int, limit: int) -> dict:
    legal_required(session, principal)
    _owned_case(session, principal, case_id)
    rows = list(session.scalars(_decision_query(principal, case_id).order_by(
        CompanyPortfolioDecision.revision.desc()).offset(offset).limit(limit + 1)))
    return {"items": [_decision_view(row) for row in rows[:limit]], "has_more": len(rows) > limit}


def record_decision(session: Session, principal: TenantPrincipal, case_id: str, payload: CompanyDecisionInput) -> dict:
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    _owned_case(session, principal, case_id, lock=True)
    prior = session.scalar(_decision_query(principal, case_id).where(CompanyPortfolioDecision.idempotency_key == payload.idempotency_key))
    if prior is not None:
        if (prior.member_id != principal.member_id or prior.action != payload.action
                or prior.rationale != payload.rationale or _utc(prior.deferred_until) != payload.deferred_until
                or prior.revision != payload.expected_revision + 1):
            raise HTTPException(409, "Idempotency key reused with a different decision")
        return _decision_view(prior)
    latest = _latest(session, principal, case_id)
    revision = latest.revision if latest else 0
    if revision != payload.expected_revision:
        raise HTTPException(409, "Company portfolio decision changed; refresh before deciding")
    if payload.deferred_until is not None and payload.deferred_until <= now_utc():
        raise HTTPException(422, "DEFER must be in the future")
    row = CompanyPortfolioDecision(case_id=case_id, tenant_id=principal.tenant_id,
                                   member_id=principal.member_id, revision=revision + 1,
                                   action=payload.action, rationale=payload.rationale,
                                   deferred_until=payload.deferred_until, idempotency_key=payload.idempotency_key)
    session.add(row)
    session.flush()
    audit(session, principal.tenant_id, "company_portfolio_decision", principal.member_id, detail=row.id)
    session.commit()
    return _decision_view(row)


InboxFilter = Literal["attention", "undecided", "deferred_due", "deferred_future", "go", "no_go", "all"]


def manager_inbox(session: Session, principal: TenantPrincipal, *, view: InboxFilter, offset: int, limit: int) -> dict:
    """Only owned saved references and current human decisions, not agent recommendations."""
    legal_required(session, principal)
    as_of = now_utc()
    latest = aliased(CompanyPortfolioDecision)
    choice = aliased(CompanyPortfolioDecision)
    latest_id = (select(choice.id).where(choice.case_id == ProcurementCase.id,
                 choice.tenant_id == principal.tenant_id).order_by(choice.revision.desc()).limit(1)
                 .correlate(ProcurementCase).scalar_subquery())
    state = sql_case((latest.id.is_(None), "undecided"),
                     (latest.action == "GO", "go"), (latest.action == "NO_GO", "no_go"),
                     (latest.deferred_until <= as_of, "deferred_due"), else_="deferred_future")
    base = (select(ProcurementCase, latest, state.label("inbox_state"))
        .join(PilotProject, PilotProject.id == ProcurementCase.project_id)
        .outerjoin(latest, latest.id == latest_id)
        .where(ProcurementCase.customer_id == principal.customer_id,
               PilotProject.customer_id == principal.customer_id,
               PilotProject.internal_slug.in_(_PROJECT_SLUGS)))
    # Counts are independent of pagination and use the same server timestamp.
    count_q = base.with_only_columns(state.label("state"), func.count()).group_by(state)
    counts = {k: 0 for k in ("undecided", "deferred_due", "deferred_future", "go", "no_go")}
    counts.update(dict(session.execute(count_q).all()))
    counts["attention"] = counts["undecided"] + counts["deferred_due"]
    counts["all"] = sum(counts[k] for k in ("undecided", "deferred_due", "deferred_future", "go", "no_go"))
    if view == "attention":
        base = base.where(state.in_(("undecided", "deferred_due")))
    elif view != "all":
        base = base.where(state == view)
    priority = sql_case((state == "deferred_due", 0), (state == "undecided", 1), else_=2)
    due_order = sql_case((state == "deferred_due", latest.deferred_until), else_=None)
    rows = session.execute(base.order_by(priority, due_order.asc().nulls_last(), ProcurementCase.created_at.desc(), ProcurementCase.id.desc()).offset(offset).limit(limit + 1)).all()
    items = [{**_case_view(session, principal, case, decision), "inbox_state": item_state} for case, decision, item_state in rows[:limit]]
    return {"customer_id": principal.customer_id, "as_of": as_of, "view": view, "offset": offset, "limit": limit,
            "summary": counts, "items": items, "has_more": len(rows) > limit,
            "scope": "SAVED_COMPANY_REFERENCES_AND_HUMAN_DECISIONS", "market_coverage_complete": False,
            "live_deadline_verified": False, "external_submission_allowed": False}
