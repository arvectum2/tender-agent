"""Canonical company-owned cases; saved EIS references are not verified facts."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.customer_pilot.models import PilotProject, ProcurementCase
from src.modules.customer_pilot.procurement_import import import_procurement_case
from src.modules.saas_foundation.models import CompanyPortfolioDecision, SaasTenant
from src.modules.saas_foundation.service import (
    TenantPrincipal,
    audit,
    legal_required,
    now_utc,
    role_required,
)

_PROJECT_SLUG = "daily-tender-company-portfolio-v1"


class SaveCompanyCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry_number: str = Field(pattern=r"^[0-9]{19,20}$")


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
    source_kind: Literal["eis_registry_reference"]
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


def _project(session: Session, principal: TenantPrincipal, *, create: bool = False):
    if create:
        tenant = session.scalar(select(SaasTenant).where(
            SaasTenant.tenant_id == principal.tenant_id,
            SaasTenant.customer_id == principal.customer_id,
        ).with_for_update())
        if tenant is None:
            raise HTTPException(404, "Company portfolio not found")
    project = session.scalar(select(PilotProject).where(
        PilotProject.customer_id == principal.customer_id,
        PilotProject.internal_slug == _PROJECT_SLUG))
    if project is None and create:
        project = PilotProject(customer_id=principal.customer_id, name="Daily Tender Run", internal_slug=_PROJECT_SLUG)
        session.add(project)
        session.flush()
    return project


def _owned_case(session: Session, principal: TenantPrincipal, case_id: str, *, lock: bool = False):
    query = select(ProcurementCase).join(PilotProject, PilotProject.id == ProcurementCase.project_id).where(
        ProcurementCase.id == case_id,
        ProcurementCase.customer_id == principal.customer_id,
        PilotProject.customer_id == principal.customer_id,
        PilotProject.internal_slug == _PROJECT_SLUG,
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
    latest = _latest(session, principal, case.id)
    return {"case_id": case.id, "registry_number": case.procurement_number,
            "source_kind": "eis_registry_reference", "source_verified": False,
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


def list_cases(session: Session, principal: TenantPrincipal, *, offset: int, limit: int) -> dict:
    legal_required(session, principal)
    project = _project(session, principal)
    cases = [] if project is None else list(session.scalars(select(ProcurementCase).where(
        ProcurementCase.customer_id == principal.customer_id, ProcurementCase.project_id == project.id,
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
