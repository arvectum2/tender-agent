"""Company case evidence: own run, exact registry, immutable profile version.

Local saved-source checks only; never fetch live EIS or invoke a model here.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.models import CompanyProfileFactVersion
from src.modules.company_profile_store.qualification_run_service import (
    assess_owned_run_qualification,
)
from src.modules.company_profile_store.service import fact_state
from src.modules.customer_onboarding.router import (
    FACT_KEY,
    OnboardingProfile,
    personalized_projection,
)
from src.modules.saas_foundation.company_portfolio import _owned_case
from src.modules.saas_foundation.models import CompanyPortfolioEvidence
from src.modules.saas_foundation.service import (
    TenantPrincipal,
    audit,
    legal_required,
    owned_run,
    role_required,
)
from src.modules.tender_operator_agent_demo.eis_archived_source_integrity import (
    verify_saved_source_snapshot,
)
from src.modules.tender_operator_agent_demo.fast_preanalysis import (
    fast_cited_preanalysis,
)
from src.modules.tender_operator_agent_demo.supplier_profile import (
    SupplierProfileCriteria,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_uploaded_demo_report,
)


class BindCaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=r"^toa-run-[0-9]{14}-[a-f0-9]{6}$")
    expected_profile_version: int = Field(ge=1)


class SearchContext(BaseModel):
    customer_id: str
    profile_version: int | None
    profile_state: str
    criteria: SupplierProfileCriteria | None
    automatic_search_enabled: bool = False


def _profile_query(principal: TenantPrincipal):
    return select(CompanyProfileFactVersion).where(
        CompanyProfileFactVersion.customer_id == principal.customer_id,
        CompanyProfileFactVersion.fact_key == FACT_KEY,
    )


def _latest_profile(session: Session, principal: TenantPrincipal):
    return session.scalar(_profile_query(principal).order_by(CompanyProfileFactVersion.version_no.desc()).limit(1))


def search_context(session: Session, principal: TenantPrincipal) -> SearchContext:
    legal_required(session, principal)
    latest = _latest_profile(session, principal)
    if latest is None:
        return SearchContext(customer_id=principal.customer_id, profile_version=None, profile_state="MISSING", criteria=None)
    _, _, state = fact_state(latest, latest_version_no=latest.version_no)
    criteria = OnboardingProfile.model_validate(latest.value_json).criteria if state == "ACTIVE" else None
    return SearchContext(customer_id=principal.customer_id, profile_version=latest.version_no,
                         profile_state=state, criteria=criteria)


def _snapshot(run_id: str, number: str | None) -> tuple[dict, str]:
    if not isinstance(number, str) or not re.fullmatch(r"[0-9]{19}", number):
        raise HTTPException(409, "Original EIS evidence binding requires a 19-digit 44-FZ reference")
    try:
        receipt = verify_saved_source_snapshot(run_id)
    except (ValueError, OSError, KeyError, HTTPException, zipfile.BadZipFile, ET.ParseError) as exc:
        raise HTTPException(409, "Saved original EIS source is unavailable or not verified") from exc
    if (receipt.get("run_id") != run_id or receipt.get("procurement_number") != number
            or receipt.get("current_live_notice_status_verified") is not False):
        raise HTTPException(409, "Saved original EIS identity does not match the case")
    fingerprint = hashlib.sha256(json.dumps(receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return receipt, fingerprint


def _scope(principal: TenantPrincipal, case_id: str):
    return select(CompanyPortfolioEvidence).where(
        CompanyPortfolioEvidence.case_id == case_id,
        CompanyPortfolioEvidence.tenant_id == principal.tenant_id,
    )


def _authorize(session: Session, principal: TenantPrincipal):
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)


def bind_evidence(session: Session, principal: TenantPrincipal, case_id: str, payload: BindCaseEvidence) -> dict:
    _authorize(session, principal)
    case = _owned_case(session, principal, case_id, lock=True)
    if not isinstance(case.procurement_number, str) or not re.fullmatch(r"[0-9]{19}", case.procurement_number):
        raise HTTPException(409, "Original EIS evidence requires an EIS case")
    owned_run(session, principal, payload.run_id)
    profile = _latest_profile(session, principal)
    if profile is None or profile.version_no != payload.expected_profile_version or fact_state(profile, latest_version_no=profile.version_no)[2] != "ACTIVE":
        raise HTTPException(409, "Active company profile changed or is missing; refresh before binding")
    OnboardingProfile.model_validate(profile.value_json)
    _, fingerprint = _snapshot(payload.run_id, case.procurement_number)
    existing = session.scalar(_scope(principal, case_id).where(CompanyPortfolioEvidence.run_id == payload.run_id,
                                                               CompanyPortfolioEvidence.profile_fact_id == profile.id))
    if existing is not None:
        if existing.source_snapshot_sha256 != fingerprint:
            raise HTTPException(409, "Previously bound source snapshot changed")
        return _binding_view(existing, profile.version_no, profile.version_no, "ACTIVE")
    row = CompanyPortfolioEvidence(case_id=case_id, tenant_id=principal.tenant_id, member_id=principal.member_id,
                                   run_id=payload.run_id, profile_fact_id=profile.id, source_snapshot_sha256=fingerprint)
    session.add(row)
    session.flush()
    audit(session, principal.tenant_id, "company_case_evidence_bound", principal.member_id, detail=row.id)
    session.commit()
    return _binding_view(row, profile.version_no, profile.version_no, "ACTIVE")


def _binding_view(row: CompanyPortfolioEvidence, version: int, current_version: int | None, state: str) -> dict:
    return {"binding_id": row.id, "case_id": row.case_id, "run_id": row.run_id,
            "profile_version": version, "current_profile_version": current_version,
            "profile_state": state, "bound_at": row.created_at,
            "source_snapshot_sha256": row.source_snapshot_sha256,
            "current_live_notice_status_verified": False, "external_action_allowed": False}


def _bound_profile(session: Session, principal: TenantPrincipal, row: CompanyPortfolioEvidence):
    profile = session.scalar(_profile_query(principal).where(CompanyProfileFactVersion.id == row.profile_fact_id))
    latest = _latest_profile(session, principal)
    if profile is None or latest is None:
        raise HTTPException(409, "Bound company profile unavailable")
    _, _, state = fact_state(profile, latest_version_no=latest.version_no)
    return profile, latest.version_no, state


def list_evidence(session: Session, principal: TenantPrincipal, case_id: str, *, offset: int, limit: int) -> dict:
    _authorize(session, principal)
    _owned_case(session, principal, case_id)
    rows = list(session.scalars(_scope(principal, case_id).order_by(
        CompanyPortfolioEvidence.created_at.desc(), CompanyPortfolioEvidence.id.desc()).offset(offset).limit(limit + 1)))
    items = []
    for row in rows[:limit]:
        owned_run(session, principal, row.run_id)
        profile, current_version, state = _bound_profile(session, principal, row)
        items.append(_binding_view(row, profile.version_no, current_version, state))
    return {"items": items, "has_more": len(rows) > limit}


def read_evidence(session: Session, principal: TenantPrincipal, case_id: str, binding_id: str) -> dict:
    _authorize(session, principal)
    case = _owned_case(session, principal, case_id)
    row = session.scalar(_scope(principal, case_id).where(CompanyPortfolioEvidence.id == binding_id))
    if row is None:
        raise HTTPException(404, "Company case evidence not found")
    owned_run(session, principal, row.run_id)
    profile, current_version, state = _bound_profile(session, principal, row)
    receipt, fingerprint = _snapshot(row.run_id, case.procurement_number)
    if fingerprint != row.source_snapshot_sha256:
        raise HTTPException(409, "Previously bound source snapshot changed")
    view = _binding_view(row, profile.version_no, current_version, state)
    # Old profile versions remain historical references, not current assessments.
    result = {**view, "archived_source_snapshot_verified": True,
              "archived_notice_version": receipt.get("archived_notice_version"),
              "screening": None, "qualification": None, "qualification_as_of": None,
              "report_status": "PROFILE_REVIEW_REQUIRED", "report_projection_is_current_not_frozen": True,
              "human_control_required": True}
    if state != "ACTIVE":
        return result
    try:
        report = get_uploaded_demo_report(row.run_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        result["report_status"] = "REPORT_UNAVAILABLE"
        return result
    if report.run_id != row.run_id:
        raise HTTPException(409, "Report run identity mismatch")
    result["screening"] = personalized_projection(principal.customer_id, profile.version_no,
        OnboardingProfile.model_validate(profile.value_json), fast_cited_preanalysis(report.decision_core, registry_number=case.procurement_number))
    as_of = datetime.now(ZoneInfo("Europe/Moscow")).date()
    result["qualification"] = assess_owned_run_qualification(session, run_id=row.run_id, customer_id=principal.customer_id, as_of=as_of)
    result["qualification_as_of"] = as_of.isoformat()
    result["report_status"] = "AVAILABLE_FOR_HUMAN_REVIEW"
    return result
