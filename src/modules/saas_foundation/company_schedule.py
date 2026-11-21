"""Explicit durable owner grants; one bounded worker tick, no daemon or token storage."""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.service import fact_state
from src.modules.daily_tender_run.service import _run_execution_guard
from src.modules.saas_foundation import company_discovery as discovery
from src.modules.saas_foundation.company_case_evidence import _latest_profile
from src.modules.saas_foundation.models import (
    CompanyDiscoverySchedule,
    SaasMember,
    SaasTenant,
)
from src.modules.saas_foundation.service import (
    PACKAGES,
    TenantPrincipal,
    _aware,
    audit,
    legal_required,
    now_utc,
    role_required,
)
from src.shared.errors import ConflictError

MAX_COMPANIES_PER_TICK = 4


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    expected_revision: int = Field(ge=0)
    expected_profile_version: int | None = Field(default=None, ge=1)
    hour_moscow: int = Field(default=8, ge=0, le=23)
    include_eis: bool = True
    commercial_indexes: list[str] = Field(default_factory=list, max_length=5)
    confirm_unattended_public_search: bool = False


def _row(session, tenant_id):
    return session.scalar(select(CompanyDiscoverySchedule).where(CompanyDiscoverySchedule.tenant_id == tenant_id).execution_options(populate_existing=True))


def _active_profile(session, principal):
    profile = _latest_profile(session, principal)
    if profile is None or fact_state(profile, latest_version_no=profile.version_no)[2] != "ACTIVE":
        raise HTTPException(409, "Active company profile required")
    return profile


def _view(session, principal, row, execution_enabled):
    profile = _latest_profile(session, principal)
    return {"customer_id": principal.customer_id, "enabled": bool(row and row.enabled),
            "execution_enabled": execution_enabled, "revision": row.revision if row else 0,
            "hour_moscow": row.hour_moscow if row else 8, "sources": row.sources_json if row else {},
            "profile_current": bool(row and profile and row.profile_fact_id == profile.id and fact_state(profile, latest_version_no=profile.version_no)[2] == "ACTIVE"),
            "last_tick_at": row.last_tick_at if row else None, "external_submission_allowed": False}


def read_schedule(session, principal, *, execution_enabled):
    legal_required(session, principal)
    return _view(session, principal, _row(session, principal.tenant_id), execution_enabled)


def update_schedule(session, principal, payload, *, execution_enabled):
    role_required(principal, "owner")
    legal_required(session, principal)
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id, SaasTenant.customer_id == principal.customer_id).with_for_update())
    if tenant is None:
        raise HTTPException(404, "Company not found")
    row = _row(session, principal.tenant_id)
    if payload.expected_revision != (row.revision if row else 0):
        raise HTTPException(409, "Schedule changed; refresh")
    profile = None
    sources = {}
    if payload.enabled:
        if not execution_enabled or not payload.confirm_unattended_public_search:
            raise HTTPException(409, "Explicit owner opt-in and server execution gate required")
        profile = _active_profile(session, principal)
        if profile.version_no != payload.expected_profile_version:
            raise HTTPException(409, "Profile changed; review before enabling schedule")
        request = discovery.StartCompanyDiscovery(expected_profile_version=profile.version_no, include_eis=payload.include_eis, commercial_indexes=payload.commercial_indexes)
        plan = discovery._plan(profile, discovery._day(), request)
        sources = {"include_eis": plan["include_eis"], "commercial_indexes": plan["commercial_indexes"]}
    if row is None:
        row = CompanyDiscoverySchedule(tenant_id=principal.tenant_id, member_id=principal.member_id, revision=0)
        session.add(row)
    row.revision += 1
    row.enabled = payload.enabled
    row.member_id = principal.member_id
    row.profile_fact_id = profile.id if profile else None
    row.sources_json = sources
    row.hour_moscow = payload.hour_moscow
    row.updated_at = now_utc()
    audit(session, principal.tenant_id, "company_schedule_updated", principal.member_id, detail=f"revision:{row.revision}:enabled:{row.enabled}")
    session.commit()
    return _view(session, principal, row, execution_enabled)


def _grant(session, tenant_id, revision):
    row = _row(session, tenant_id)
    if not row or not row.enabled or row.revision != revision:
        raise HTTPException(409, "Schedule disabled or changed")
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant_id).execution_options(populate_existing=True))
    member = session.scalar(select(SaasMember).where(SaasMember.id == row.member_id, SaasMember.tenant_id == tenant_id).execution_options(populate_existing=True))
    if not tenant or tenant.lifecycle != "active" or tenant.plan_code not in PACKAGES or not member or not member.active or member.role != "owner":
        raise HTTPException(403, "Schedule owner or company inactive")
    if tenant.billing_state not in {"trial", "verified_manual_payment"} or (tenant.billing_state == "trial" and _aware(tenant.trial_ends_at) <= now_utc()):
        raise HTTPException(402, "Schedule entitlement inactive")
    # Explicit durable owner grant, not a minted or persisted Bearer credential.
    principal = TenantPrincipal(tenant_id, tenant.customer_id, member.id, member.role, "schedule-grant")
    legal_required(session, principal)
    profile = _active_profile(session, principal)
    if profile.id != row.profile_fact_id:
        raise HTTPException(409, "Schedule profile changed; owner review required")
    return row, principal, profile


def execution_enabled(settings):
    return bool(settings.saas_foundation_enabled and settings.saas_company_discovery_enabled and settings.saas_company_schedule_enabled)


def tick(session: Session, settings, *, limit=MAX_COMPANIES_PER_TICK):
    if not execution_enabled(settings):
        return {"enabled": False, "considered": 0, "outcomes": {}}
    if not 1 <= limit <= MAX_COMPANIES_PER_TICK:
        raise ValueError("Invalid tick company limit")
    outcomes = {}
    def count(status):
        outcomes[status] = outcomes.get(status, 0) + 1
    try:
        with _run_execution_guard(session, "company-discovery-schedule-tick"):
            rows = list(session.execute(select(CompanyDiscoverySchedule.tenant_id, CompanyDiscoverySchedule.revision).where(CompanyDiscoverySchedule.enabled.is_(True), CompanyDiscoverySchedule.hour_moscow <= now_utc().astimezone(discovery.MOSCOW).hour).order_by(CompanyDiscoverySchedule.last_tick_at.asc().nullsfirst(), CompanyDiscoverySchedule.tenant_id).limit(limit)))
            for tenant_id, revision in rows:
                try:
                    row = _row(session, tenant_id)
                    if not row or row.revision != revision or not row.enabled:
                        count("grant_changed")
                        continue
                    row.last_tick_at = now_utc()
                    session.commit()
                    row, principal, profile = _grant(session, tenant_id, revision)
                    request = discovery.StartCompanyDiscovery(expected_profile_version=profile.version_no, **row.sources_json)
                    run = discovery.create_run(session, principal, request)
                    if run["status"] not in {"PENDING", "IN_PROGRESS"}:
                        count("already_finished")
                        continue
                    def authorize(s, tenant_id=tenant_id, revision=revision):
                        _grant(s, tenant_id, revision)
                    updated = discovery.advance_run(session, principal, run["run_id"], discovery.AdvanceCompanyDiscovery(expected_step=run["completed_steps"]), scheduled=True, authorize=authorize)
                    count(updated["status"])
                except HTTPException as exc:
                    session.rollback()
                    count(f"blocked_{exc.status_code}")
                finally:
                    session.rollback()
            return {"enabled": True, "considered": len(rows), "outcomes": outcomes}
    except ConflictError:
        return {"enabled": True, "considered": 0, "outcomes": {"worker_busy": 1}}
