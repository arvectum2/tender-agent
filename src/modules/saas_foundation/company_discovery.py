"""Opt-in company search: durable bounded steps, no global profile or Deal mutation."""
from __future__ import annotations

import math
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.service import fact_state
from src.modules.customer_onboarding.router import OnboardingProfile
from src.modules.daily_tender_run.service import _run_execution_guard
from src.modules.saas_foundation.company_case_evidence import _latest_profile
from src.modules.saas_foundation.models import CompanyDiscoveryRun, SaasTenant
from src.modules.saas_foundation.service import (
    TenantPrincipal,
    audit,
    legal_required,
    now_utc,
    role_required,
)
from src.modules.tender_operator_agent_demo.procurement_discovery import (
    search_public_44fz,
)
from src.shared.errors import ConflictError

MAX_STEPS = 8
MAX_CARDS = 10
MOSCOW = ZoneInfo("Europe/Moscow")


class StartCompanyDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_profile_version: int = Field(ge=1)


class AdvanceCompanyDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_step: int = Field(ge=0, le=MAX_STEPS)


def _day():
    return now_utc().astimezone(MOSCOW).date()


def _validate_terms(values, *, max_length=160):
    terms = list(dict.fromkeys(v.strip() for v in values if v.strip()))
    if any(len(v) > max_length for v in terms):
        raise HTTPException(422, "Search criterion exceeds bounded length")
    return terms


def _plan(profile, day):
    criteria = OnboardingProfile.model_validate(profile.value_json).criteria
    keywords = _validate_terms(criteria.keywords)
    regions = _validate_terms(criteria.regions)
    exclusions = _validate_terms([*criteria.stop_words, *criteria.excluded_categories])
    if not keywords or len(keywords) * max(len(regions), 1) > MAX_STEPS or len(exclusions) > 50:
        raise HTTPException(422, "Set explicit keywords; at most 8 keyword/region combinations and 50 exclusions per pilot day")
    lo, hi = criteria.price_min, criteria.price_max
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in (lo, hi)) or (lo is not None and hi is not None and lo > hi):
        raise HTTPException(422, "Invalid company price criteria")
    return {"profile_version": profile.version_no, "date_from": (day - timedelta(days=2)).isoformat(),
            "date_to": day.isoformat(), "law": "44fz", "price_min": lo, "price_max": hi,
            "excluded_title_terms": exclusions, "steps": [{"query": k, "region": r} for k in keywords for r in regions or [None]],
            "search_limitations": ["44fz_only", "bounded_first_results", "literal_title_exclusions_only", "category_and_qualification_review_required", "region_filter_not_independently_verified", "no_live_notice_status_verification"]}


def _query(principal):
    return select(CompanyDiscoveryRun).where(CompanyDiscoveryRun.tenant_id == principal.tenant_id)


def _owned(session, principal, run_id):
    row = session.scalar(_query(principal).where(CompanyDiscoveryRun.id == run_id).execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Company discovery run not found")
    return row


def _view(row, principal):
    candidates = {}
    for step in row.results_json:
        for candidate in step["candidates"]:
            number = candidate["registry_number"]
            if number not in candidates:
                candidates[number] = {**candidate, "matched_steps": [step["step"]]}
            else:
                candidates[number]["matched_steps"].append(step["step"])
    return {"run_id": row.id, "customer_id": principal.customer_id, "status": row.status,
            "run_day": row.run_day, "plan": row.plan_json, "completed_steps": len(row.results_json),
            "step_receipts": row.results_json, "candidates": list(candidates.values()),
            "discovery_incomplete": row.status != "COMPLETED", "external_submission_allowed": False,
            "automatic_scheduling_enabled": False}


def create_run(session: Session, principal: TenantPrincipal, payload: StartCompanyDiscovery):
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id, SaasTenant.customer_id == principal.customer_id).with_for_update())
    if tenant is None:
        raise HTTPException(404, "Company not found")
    day = _day()
    profile = _latest_profile(session, principal)
    if profile is None or profile.version_no != payload.expected_profile_version or fact_state(profile, latest_version_no=profile.version_no)[2] != "ACTIVE":
        raise HTTPException(409, "Current active profile required")
    existing = session.scalar(_query(principal).where(CompanyDiscoveryRun.run_day == day.isoformat()))
    if existing is not None:
        if existing.profile_fact_id != profile.id:
            raise HTTPException(409, "Today's discovery used a different profile; next daily run required")
        return _view(existing, principal)
    row = CompanyDiscoveryRun(tenant_id=principal.tenant_id, member_id=principal.member_id, profile_fact_id=profile.id,
                              run_day=day.isoformat(), plan_json=_plan(profile, day), results_json=[])
    session.add(row)
    session.flush()
    audit(session, principal.tenant_id, "company_discovery_planned", principal.member_id, detail=row.id)
    session.commit()
    return _view(row, principal)


def read_run(session: Session, principal: TenantPrincipal, run_id: str):
    legal_required(session, principal)
    return _view(_owned(session, principal, run_id), principal)


def latest_run(session: Session, principal: TenantPrincipal):
    legal_required(session, principal)
    row = session.scalar(_query(principal).order_by(CompanyDiscoveryRun.run_day.desc()).limit(1))
    return _view(row, principal) if row else None


def _receipt(plan, index, payload):
    outcome = payload.get("outcome") if isinstance(payload, dict) else None
    cards = payload.get("cards") if isinstance(payload, dict) else None
    valid_outcomes = {"success_empty", "success_with_results", "source_unavailable", "source_not_configured", "source_error", "unsupported_search_mode", "validation_error"}
    if not isinstance(outcome, str) or outcome not in valid_outcomes:
        outcome = "invalid_search_response"
    receipt = {"step": index, "query": plan["steps"][index]["query"], "region": plan["steps"][index]["region"],
               "outcome": outcome, "coverage_complete": False, "invalid_cards": 0, "excluded_cards": 0,
               "candidates": [], "observed_at": now_utc().isoformat()}
    if outcome not in {"success_empty", "success_with_results"}:
        return receipt
    if not isinstance(cards, list) or bool(cards) != (outcome == "success_with_results") or payload.get("source") != "public_eis_html_44fz":
        receipt["outcome"] = "invalid_search_response"
        return receipt
    seen = set()
    for card in cards[:MAX_CARDS]:
        if not isinstance(card, dict):
            receipt["invalid_cards"] += 1
            continue
        number = card.get("reestr_number") or card.get("notice_number")
        title = card.get("title")
        if (not isinstance(number, str) or not re.fullmatch(r"[0-9]{19}", number)
                or not isinstance(title, str) or not title.strip()
                or card.get("source") != "public_eis_html_44fz" or card.get("law") != "44fz"):
            receipt["invalid_cards"] += 1
            continue
        if number in seen:
            continue
        seen.add(number)
        if any(term.casefold() in title.casefold() for term in plan["excluded_title_terms"]):
            receipt["excluded_cards"] += 1
            continue
        price = card.get("initial_price")
        if isinstance(price, bool) or not isinstance(price, (float, int)) or not math.isfinite(price) or price < 0:
            price = None
        if price is not None and ((plan["price_min"] is not None and price < plan["price_min"]) or (plan["price_max"] is not None and price > plan["price_max"])):
            receipt["excluded_cards"] += 1
            continue
        receipt["candidates"].append({"registry_number": number, "title": title[:500], "observed_price": price,
                                      "source": "public_eis_html_44fz", "source_verified": False,
                                      "human_review_required": True})
    receipt["coverage_complete"] = bool(payload.get("source_coverage_complete") is True and payload.get("has_more") is False
                                        and len(cards) <= MAX_CARDS and not receipt["invalid_cards"])
    return receipt


def _check_window(session, principal, row):
    if row.run_day != _day().isoformat():
        row.status = "EXPIRED_WINDOW"
    else:
        profile = _latest_profile(session, principal)
        if profile is None or profile.id != row.profile_fact_id or fact_state(profile, latest_version_no=profile.version_no)[2] != "ACTIVE":
            row.status = "STALE_PROFILE"
    if row.status in {"STALE_PROFILE", "EXPIRED_WINDOW"}:
        row.updated_at = now_utc()
        session.commit()
        return False
    return True


def advance_run(session: Session, principal: TenantPrincipal, run_id: str, payload: AdvanceCompanyDiscovery):
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    _owned(session, principal, run_id)
    # Existing tested advisory guard; a committed step is never re-fetched on replay.
    try:
        with _run_execution_guard(session, "company-discovery:" + run_id):
            row = _owned(session, principal, run_id)
            index = len(row.results_json)
            if payload.expected_step < index:
                return _view(row, principal)
            if payload.expected_step != index:
                raise HTTPException(409, "Refresh discovery checkpoint")
            if row.status not in {"PENDING", "IN_PROGRESS"} or not _check_window(session, principal, row):
                return _view(row, principal)
            plan = row.plan_json
            step = plan["steps"][index]
            # Release the read transaction while the public HTTP request runs.
            session.rollback()
            try:
                result = search_public_44fz(query=step["query"], law="44fz", region=step["region"],
                    date_from=plan["date_from"], date_to=plan["date_to"], price_from=plan["price_min"],
                    price_to=plan["price_max"], status_filter="Подача заявок", reference_date=_day(),
                    page=1, page_size=MAX_CARDS, max_results=MAX_CARDS, apply_supplier_relevance=False, backfill_page_limit=2)
            except Exception:  # noqa: BLE001 - record only safe source outcome, never raw exception or URL
                result = {"outcome": "source_error"}
            row = _owned(session, principal, run_id)
            if not _check_window(session, principal, row):
                return _view(row, principal)
            receipt = _receipt(plan, index, result)
            row.results_json = [*row.results_json, receipt]
            if len(row.results_json) == len(plan["steps"]):
                row.status = "COMPLETED" if all(r["coverage_complete"] for r in row.results_json) else "PARTIAL"
            else:
                row.status = "IN_PROGRESS"
            row.updated_at = now_utc()
            audit(session, principal.tenant_id, "company_discovery_step", principal.member_id, detail=f"{row.id}:{index}:{receipt['outcome']}")
            session.commit()
            return _view(row, principal)
    except ConflictError as exc:
        raise HTTPException(409, "Company discovery already executing") from exc
