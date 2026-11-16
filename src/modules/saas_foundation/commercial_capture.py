"""Explicit bounded public card capture; no arbitrary URLs or client HTML."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

import httpx
from fastapi import HTTPException
from lxml.etree import LxmlError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from src.modules.saas_foundation.commercial_attachment_inventory import (
    attachment_inventory,
)
from src.modules.saas_foundation.commercial_card_evidence import (
    MAX_CARD_BYTES,
    MOSCOW,
    verify_card_snapshot,
)
from src.modules.saas_foundation.commercial_sources import commercial_identity
from src.modules.saas_foundation.company_portfolio import _owned_case, _view
from src.modules.saas_foundation.models import (
    CommercialCaptureAttempt,
    CommercialCardSnapshot,
    SaasAccessToken,
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

MAX_DAILY_PER_TENANT = 10
MAX_CAPTURE_SECONDS = 20


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_public_capture: bool = Field(strict=True)


@dataclass(frozen=True)
class SourceResponse:
    url: str
    content_type: str
    status_code: int
    observed_at: datetime
    raw: bytes


def fetch_card(url: str) -> SourceResponse:
    commercial_identity(url)
    started = monotonic()
    # Explicit TLS, no ambient proxy or auth, no redirects or subresource requests.
    with (httpx.Client(verify=True, trust_env=False, follow_redirects=False, timeout=httpx.Timeout(5.0, connect=5.0)) as client,
          client.stream("GET", url, headers={"Accept": "text/html", "Accept-Encoding": "identity"}) as response):
        if response.status_code != 200 or str(response.url) != url:
            raise ValueError("Unexpected public card response")
        mime = response.headers.get("content-type", "")
        if mime.split(";", 1)[0].strip().lower() != "text/html" or response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Unsupported public card response encoding")
        raw = bytearray()
        for chunk in response.iter_raw():
            if monotonic() - started > MAX_CAPTURE_SECONDS or len(raw) + len(chunk) > MAX_CARD_BYTES:
                raise ValueError("Public card response bound exceeded")
            raw.extend(chunk)
        if monotonic() - started > MAX_CAPTURE_SECONDS:
            raise ValueError("Public card response bound exceeded")
        return SourceResponse(url, mime, response.status_code, now_utc(), bytes(raw))


def _authorized(session: Session, principal: TenantPrincipal):
    token = session.get(SaasAccessToken, principal.token_id, populate_existing=True)
    member = session.get(SaasMember, principal.member_id, populate_existing=True)
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id).execution_options(populate_existing=True))
    if (not token or token.revoked_at or _aware(token.expires_at) <= now_utc()
            or token.member_id != principal.member_id or token.tenant_id != principal.tenant_id
            or not member or not member.active or member.tenant_id != principal.tenant_id):
        raise HTTPException(401, "Capture authorization expired")
    if not tenant or tenant.customer_id != principal.customer_id or tenant.lifecycle != "active" or tenant.plan_code not in PACKAGES:
        raise HTTPException(403, "Capture company inactive")
    if tenant.billing_state not in {"trial", "verified_manual_payment"} or (tenant.billing_state == "trial" and _aware(tenant.trial_ends_at) <= now_utc()):
        raise HTTPException(402, "Capture entitlement inactive")
    if member.role not in {"owner", "admin", "analyst"}:
        raise HTTPException(403, "Capture role insufficient")
    legal_required(session, principal)


def _reference(session, principal, case_id):
    view = _view(session, principal, _owned_case(session, principal, case_id))
    url = view.get("source_url")
    if view["source_kind"] != "commercial_reference" or not url:
        raise HTTPException(409, "Exact saved commercial reference required")
    return url


def _view_capture(attempt, snapshot):
    return {"attempt_id": attempt.id, "case_id": attempt.case_id, "capture_day": attempt.capture_day,
            "source_url": attempt.source_url, "outcome": snapshot.outcome if snapshot else "UNCONFIRMED_ATTEMPT",
            "snapshot_id": snapshot.id if snapshot else None, "receipt": snapshot.receipt_json if snapshot else None,
            "current_live_notice_status_verified": False, "external_submission_allowed": False}


def _attempts(principal, case_id):
    return select(CommercialCaptureAttempt, CommercialCardSnapshot).outerjoin(CommercialCardSnapshot, CommercialCardSnapshot.attempt_id == CommercialCaptureAttempt.id).where(CommercialCaptureAttempt.tenant_id == principal.tenant_id, CommercialCaptureAttempt.case_id == case_id)


def capture(session, principal, case_id, payload):
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    if not payload.confirm_public_capture:
        raise HTTPException(422, "Explicit public capture confirmation required")
    url = _reference(session, principal, case_id)
    # Serialize admission, not I/O. Unconfirmed reservations consume the budget.
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id, SaasTenant.customer_id == principal.customer_id).with_for_update())
    if tenant is None:
        raise HTTPException(404, "Company not found")
    _authorized(session, principal)
    day = now_utc().astimezone(MOSCOW).date().isoformat()
    existing = session.execute(_attempts(principal, case_id).where(CommercialCaptureAttempt.capture_day == day).options(defer(CommercialCardSnapshot.original_html))).one_or_none()
    if existing:
        return _view_capture(*existing)
    count = session.scalar(select(func.count()).select_from(CommercialCaptureAttempt).where(CommercialCaptureAttempt.tenant_id == principal.tenant_id, CommercialCaptureAttempt.capture_day == day))
    if count >= MAX_DAILY_PER_TENANT:
        raise HTTPException(429, "Daily commercial capture budget reached")
    attempt = CommercialCaptureAttempt(tenant_id=principal.tenant_id, member_id=principal.member_id, case_id=case_id, capture_day=day, source_url=url)
    session.add(attempt)
    session.flush()
    attempt_id = attempt.id
    audit(session, principal.tenant_id, "commercial_capture_reserved", principal.member_id, detail=attempt_id)
    session.commit()
    raw, receipt = None, None
    try:
        response = fetch_card(url)
    except (httpx.HTTPError, ValueError, OSError):
        outcome = "SOURCE_UNAVAILABLE"
    else:
        try:
            receipt = verify_card_snapshot(requested_url=url, final_url=response.url, status_code=response.status_code,
                                           tls_verified=True, content_type=response.content_type, raw=response.raw, observed_at=response.observed_at)
            raw = response.raw
            outcome = "CAPTURED"
        except (ValueError, LxmlError):
            outcome = "UNSUPPORTED_CARD"
    _authorized(session, principal)
    if _reference(session, principal, case_id) != url:
        raise HTTPException(409, "Saved commercial reference changed")
    stored = session.get(CommercialCaptureAttempt, attempt_id)
    snapshot = CommercialCardSnapshot(attempt_id=attempt_id, outcome=outcome, original_html=raw, receipt_json=receipt)
    session.add(snapshot)
    audit(session, principal.tenant_id, "commercial_capture_outcome", principal.member_id, detail=f"{attempt_id}:{outcome}")
    session.commit()
    return _view_capture(stored, snapshot)


def list_captures(session, principal, case_id, *, offset, limit):
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    _reference(session, principal, case_id)
    rows = list(session.execute(_attempts(principal, case_id).options(defer(CommercialCardSnapshot.original_html)).order_by(CommercialCaptureAttempt.created_at.desc(), CommercialCaptureAttempt.id.desc()).offset(offset).limit(limit + 1)))
    return {"customer_id": principal.customer_id, "case_id": case_id, "items": [_view_capture(*row) for row in rows[:limit]], "has_more": len(rows) > limit}


def recheck(session, principal, case_id, attempt_id):
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    url = _reference(session, principal, case_id)
    row = session.execute(_attempts(principal, case_id).where(CommercialCaptureAttempt.id == attempt_id)).one_or_none()
    if row is None:
        raise HTTPException(404, "Capture not found")
    attempt, snapshot = row
    result = _view_capture(attempt, snapshot)
    result["original_reverified"] = False
    if snapshot and snapshot.outcome == "CAPTURED":
        try:
            if url != attempt.source_url or not isinstance(snapshot.receipt_json, dict):
                raise ValueError("Source mismatch")
            verified = verify_card_snapshot(requested_url=attempt.source_url, final_url=attempt.source_url, status_code=200,
                        tls_verified=True, content_type="text/html", raw=snapshot.original_html,
                        observed_at=datetime.fromisoformat(snapshot.receipt_json["observed_at"]).astimezone(UTC))
            if verified != snapshot.receipt_json:
                raise ValueError("Stored receipt mismatch")
            result["attachment_inventory"] = attachment_inventory(attempt.source_url, snapshot.original_html)
        except (ValueError, TypeError, KeyError, LxmlError) as exc:
            raise HTTPException(409, "Stored public card integrity mismatch") from exc
        result["original_reverified"] = True
    return result


def compare_captures(session, principal, case_id, attempt_id, previous_attempt_id):
    """Compare two historical observations only, never infer why a change occurred."""
    if previous_attempt_id == attempt_id:
        raise HTTPException(422, 'Choose two different capture attempts')
    current = recheck(session, principal, case_id, attempt_id)
    previous = recheck(session, principal, case_id, previous_attempt_id)
    if not current['original_reverified'] or not previous['original_reverified']:
        raise HTTPException(409, 'Two verified historical originals required')
    before, after = previous['receipt'], current['receipt']
    if datetime.fromisoformat(before['observed_at']) >= datetime.fromisoformat(after['observed_at']):
        raise HTTPException(422, 'Previous observation must be older')
    fields = ('title', 'displayed_stage', 'displayed_deadline', 'deadline_precision', 'organizer_type', 'organizer_name_literal')
    changes = {k: {'before': before[k], 'after': after[k]} for k in fields if before[k] != after[k]}
    old_links = {r['source_url']: r for r in previous['attachment_inventory']['candidates']}
    new_links = {r['source_url']: r for r in current['attachment_inventory']['candidates']}
    current['comparison'] = {'previous_attempt_id': previous_attempt_id, 'previous_observed_at': before['observed_at'],
        'html_changed': before['html_sha256'] != after['html_sha256'], 'observed_field_changes': changes,
        'candidate_links_added': [new_links[u] for u in sorted(new_links.keys()-old_links.keys())],
        'candidate_links_absent': [old_links[u] for u in sorted(old_links.keys()-new_links.keys())],
        'candidate_link_coverage_complete': False, 'attachment_bytes_compared': False,
        'current_live_notice_status_verified': False, 'external_submission_allowed': False}
    return current
