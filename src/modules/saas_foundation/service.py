"""APR-05 tenant auth, operator bootstrap, quota accounting and legal HUMAN gates."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.customer_registry.models import CustomerProfile
from src.modules.saas_foundation.models import (
    SaasAccessToken,
    SaasAuditEvent,
    SaasInvitation,
    SaasLegalAcceptance,
    SaasMember,
    SaasPaymentEvidence,
    SaasRun,
    SaasTenant,
    SaasUsageCounter,
)

TERMS_VERSION = "APR05-INTERNAL-PILOT-TERMS-v1"
PRIVACY_VERSION = "APR05-INTERNAL-PILOT-DATA-v1"
ROLES = ("owner", "admin", "analyst", "viewer")
# These are engineering limits, NOT approved public prices or payment terms.
PACKAGES = {
    "pilot": {"name": "Pilot (internal trial)", "quota": {"screens": 30, "documents": 12, "runs": 8, "analyses": 8}, "price_rub": None, "seats": 3},
    "team": {"name": "Team (draft)", "quota": {"screens": 150, "documents": 60, "runs": 40, "analyses": 40}, "price_rub": None, "seats": 15},
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def _aware(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def random_secret(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(36)}"


def audit(session: Session, tenant_id: str, event: str, member_id: str | None = None, detail: str = "") -> None:
    session.add(SaasAuditEvent(
        tenant_id=tenant_id, member_id=member_id, event_type=event,
        detail=detail[:1000],
    ))


@dataclass(frozen=True)
class TenantPrincipal:
    tenant_id: str
    customer_id: str
    member_id: str
    role: str
    token_id: str


def require_tenant(session: Session, token: str | None) -> TenantPrincipal:
    if not token or not token.startswith("saas_") or len(token) > 160:
        raise HTTPException(401, "Valid tenant bearer token required")
    stored = session.scalar(select(SaasAccessToken).where(SaasAccessToken.token_sha256 == digest(token)))
    if not stored or stored.revoked_at or _aware(stored.expires_at) <= now_utc():
        raise HTTPException(401, "Token expired or invalid")
    member = session.scalar(select(SaasMember).where(SaasMember.id == stored.member_id))
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == stored.tenant_id))
    if not member or not member.active or not tenant or member.tenant_id != tenant.tenant_id:
        raise HTTPException(401, "Tenant identity disabled")
    if tenant.lifecycle != "active":
        raise HTTPException(403, "Tenant suspended")
    if tenant.plan_code not in PACKAGES:
        raise HTTPException(403, "Tenant plan invalid")
    if tenant.billing_state == "trial" and _aware(tenant.trial_ends_at) <= now_utc():
        raise HTTPException(402, "Trial expired; payment verification required")
    if tenant.billing_state not in {"trial", "verified_manual_payment"}:
        raise HTTPException(402, "No active entitlement")
    return TenantPrincipal(tenant.tenant_id, tenant.customer_id, member.id, member.role, stored.id)


def role_required(principal: TenantPrincipal, *allowed: str) -> None:
    if principal.role not in allowed:
        raise HTTPException(403, "Tenant role insufficient")


def legal_required(session: Session, principal: TenantPrincipal) -> None:
    accepted = session.scalar(
        select(SaasLegalAcceptance).where(
            SaasLegalAcceptance.tenant_id == principal.tenant_id,
            SaasLegalAcceptance.member_id == principal.member_id,
            SaasLegalAcceptance.terms_version == TERMS_VERSION,
            SaasLegalAcceptance.privacy_version == PRIVACY_VERSION,
        )
    )
    if not accepted:
        raise HTTPException(428, "Current pilot terms and privacy acknowledgement required")


def create_tenant(session: Session, *, customer_id: str, plan_code: str = "pilot") -> dict:
    if plan_code not in PACKAGES:
        raise HTTPException(422, "Unknown plan")
    if not session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer_id)):
        raise HTTPException(404, "Company does not exist")
    if session.scalar(select(SaasTenant).where(SaasTenant.customer_id == customer_id)):
        raise HTTPException(409, "Customer is already bound to a SaaS tenant")
    tenant = SaasTenant(
        tenant_id="ten_" + uuid4().hex,
        customer_id=customer_id, plan_code=plan_code,
        lifecycle="active", billing_state="trial",
        trial_ends_at=now_utc() + timedelta(days=14),
    )
    session.add(tenant)
    session.flush()
    invite = issue_invitation(session, tenant.tenant_id, role="owner",
                              acquisition_channel="operator", commit=False)
    audit(session, tenant.tenant_id, "tenant_bootstrapped")
    session.commit()
    return {
        "tenant_id": tenant.tenant_id, "customer_id": tenant.customer_id,
        "plan_code": tenant.plan_code, "billing_state": tenant.billing_state,
        "trial_ends_at": tenant.trial_ends_at.isoformat(),
        "invitation": invite,
        "payment_collected": False,
    }


def issue_invitation(
    session: Session, tenant_id: str, *, role: str, acquisition_channel: str,
    actor_id: str | None = None, commit: bool = True,
) -> dict:
    if role not in ROLES:
        raise HTTPException(422, "Invalid role")
    tenant = session.scalar(
        select(SaasTenant).where(SaasTenant.tenant_id == tenant_id).with_for_update()
    )
    if not tenant or tenant.lifecycle != "active":
        raise HTTPException(403, "Tenant unavailable")
    seats = PACKAGES[tenant.plan_code]["seats"]
    active = session.scalar(
        select(func.count()).select_from(SaasMember).where(
            SaasMember.tenant_id == tenant_id, SaasMember.active.is_(True)
        )
    ) or 0
    pending = list(session.scalars(
        select(SaasInvitation).where(
            SaasInvitation.tenant_id == tenant_id,
            SaasInvitation.consumed_at.is_(None),
        )
    ))
    unexpired_pending = sum(_aware(item.expires_at) > now_utc() for item in pending)
    if active + unexpired_pending >= seats:
        raise HTTPException(429, "Tenant seat entitlement exceeded")
    token = random_secret("invite")
    expires_at = now_utc() + timedelta(days=7)
    session.add(SaasInvitation(
        tenant_id=tenant_id, role=role, token_sha256=digest(token),
        issued_by_member_id=actor_id, acquisition_channel=acquisition_channel,
        expires_at=expires_at,
    ))
    audit(session, tenant_id, "invite_issued", actor_id, detail=f"{role}:{acquisition_channel}")
    if commit:
        session.commit()
    return {"invitation_code": token, "role": role,
            "expires_at": expires_at.isoformat(), "one_time": True}


def redeem_invitation(session: Session, code: str, display_name: str) -> dict:
    if not code.startswith("invite_") or len(code) > 160:
        raise HTTPException(400, "Invalid invitation")
    invite = session.scalar(
        select(SaasInvitation).where(SaasInvitation.token_sha256 == digest(code)).with_for_update()
    )
    if not invite or invite.consumed_at or _aware(invite.expires_at) <= now_utc():
        raise HTTPException(410, "Invitation invalid, used or expired")
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == invite.tenant_id))
    if not tenant or tenant.lifecycle != "active":
        raise HTTPException(403, "Tenant unavailable")
    invite.consumed_at = now_utc()
    member = SaasMember(tenant_id=tenant.tenant_id,
                        display_name=display_name.strip(), role=invite.role, active=True)
    session.add(member)
    session.flush()
    raw = random_secret("saas")
    expires_at = now_utc() + timedelta(days=14)
    session.add(SaasAccessToken(
        tenant_id=tenant.tenant_id, member_id=member.id,
        token_sha256=digest(raw), expires_at=expires_at,
    ))
    audit(session, tenant.tenant_id, "invite_redeemed", member.id,
          detail=f"role:{member.role}")
    session.commit()
    return {
        "access_token": raw, "token_type": "Bearer",
        "expires_at": expires_at.isoformat(),
        "tenant_id": tenant.tenant_id, "member_id": member.id,
        "role": member.role, "show_token_once": True,
    }


def accept_terms(session: Session, principal: TenantPrincipal, *, terms: str, privacy: str) -> dict:
    if terms != TERMS_VERSION or privacy != PRIVACY_VERSION:
        raise HTTPException(409, "Current internal pilot policy version required")
    already = session.scalar(select(SaasLegalAcceptance).where(
        SaasLegalAcceptance.member_id == principal.member_id,
        SaasLegalAcceptance.terms_version == terms,
        SaasLegalAcceptance.privacy_version == privacy,
    ))
    if already:
        return {"accepted": True, "terms_version": terms, "privacy_version": privacy}
    session.add(SaasLegalAcceptance(
        tenant_id=principal.tenant_id, member_id=principal.member_id,
        terms_version=terms, privacy_version=privacy,
    ))
    audit(session, principal.tenant_id, "terms_acknowledged", principal.member_id,
          detail=f"{terms}/{privacy}")
    session.commit()
    return {"accepted": True, "terms_version": terms, "privacy_version": privacy,
            "not_a_digital_signature": True}


def _entitlement(session: Session, principal: TenantPrincipal, metric: str) -> tuple[SaasTenant, int]:
    legal_required(session, principal)
    tenant = session.scalar(
        select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id).with_for_update()
    )
    if not tenant or tenant.lifecycle != "active":
        raise HTTPException(403, "Tenant suspended")
    if tenant.billing_state == "trial" and _aware(tenant.trial_ends_at) <= now_utc():
        raise HTTPException(402, "Trial expired")
    if tenant.billing_state not in {"trial", "verified_manual_payment"}:
        raise HTTPException(402, "Payment or active trial required")
    quota = PACKAGES.get(tenant.plan_code, {}).get("quota", {}).get(metric)
    if quota is None:
        raise HTTPException(403, "Metric not included in tenant plan")
    return tenant, quota


def charge(session: Session, principal: TenantPrincipal, metric: str) -> dict:
    tenant, limit = _entitlement(session, principal, metric)
    period = now_utc().strftime("%Y-%m")
    row = session.scalar(select(SaasUsageCounter).where(
        SaasUsageCounter.tenant_id == principal.tenant_id,
        SaasUsageCounter.period_utc == period,
        SaasUsageCounter.metric == metric,
    ).with_for_update())
    if not row:
        row = SaasUsageCounter(tenant_id=principal.tenant_id, period_utc=period,
                               metric=metric, used=0)
        session.add(row)
        session.flush()
    if row.used >= limit:
        session.rollback()
        raise HTTPException(429, f"Monthly {metric} quota exhausted")
    row.used += 1
    audit(session, tenant.tenant_id, "usage_reserved", principal.member_id,
          detail=f"{metric}:{period}")
    session.commit()
    return {"metric": metric, "period": period, "used": row.used, "limit": limit}


def refund(session: Session, principal: TenantPrincipal, metric: str) -> None:
    period = now_utc().strftime("%Y-%m")
    tenant = session.scalar(
        select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id).with_for_update()
    )
    if tenant is None:
        return
    row = session.scalar(select(SaasUsageCounter).where(
        SaasUsageCounter.tenant_id == principal.tenant_id,
        SaasUsageCounter.period_utc == period,
        SaasUsageCounter.metric == metric,
    ).with_for_update())
    if row and row.used:
        row.used -= 1
    audit(session, principal.tenant_id, "usage_refunded", principal.member_id,
          detail=f"{metric}:{period}")
    session.commit()


def usage_view(session: Session, principal: TenantPrincipal) -> dict:
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id))
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    period = now_utc().strftime("%Y-%m")
    rows = list(session.scalars(select(SaasUsageCounter).where(
        SaasUsageCounter.tenant_id == principal.tenant_id, SaasUsageCounter.period_utc == period
    )))
    used = {row.metric: row.used for row in rows}
    quotas = PACKAGES[tenant.plan_code]["quota"]
    return {
        "period_utc": period, "billing_state": tenant.billing_state,
        "plan": tenant.plan_code, "trial_ends_at": tenant.trial_ends_at.isoformat(),
        "metrics": {k: {"used": used.get(k, 0), "limit": v,
                         "remaining": max(0, v - used.get(k, 0))} for k, v in quotas.items()},
        "no_live_charging": True,
    }


def owned_run(session: Session, principal: TenantPrincipal, run_id: str) -> SaasRun:
    run = session.scalar(select(SaasRun).where(
        SaasRun.tenant_id == principal.tenant_id, SaasRun.run_id == run_id,
    ))
    if not run:
        raise HTTPException(404, "No tenant-owned run with that identifier")
    return run


def overview(session: Session, principal: TenantPrincipal) -> dict:
    legal = session.scalar(select(SaasLegalAcceptance).where(
        SaasLegalAcceptance.member_id == principal.member_id,
        SaasLegalAcceptance.terms_version == TERMS_VERSION,
        SaasLegalAcceptance.privacy_version == PRIVACY_VERSION,
    ))
    members = session.scalar(select(func.count()).select_from(SaasMember).where(
        SaasMember.tenant_id == principal.tenant_id, SaasMember.active.is_(True)
    ))
    runs = session.scalar(select(func.count()).select_from(SaasRun).where(
        SaasRun.tenant_id == principal.tenant_id
    ))
    claimed = session.scalar(select(func.count()).select_from(SaasInvitation).where(
        SaasInvitation.tenant_id == principal.tenant_id,
        SaasInvitation.consumed_at.is_not(None),
    ))
    return {
        "tenant_id": principal.tenant_id, "role": principal.role,
        "customer_id": principal.customer_id, "member_id": principal.member_id,
        "legal_accepted": bool(legal), "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "usage": usage_view(session, principal),
        "acquisition": {"activated_members": members, "invites_redeemed": claimed},
        "product_metrics": {"owned_tender_runs": runs},
        "human_control_required": True, "external_action_allowed": False,
    }


def verify_manual_payment(session: Session, tenant_id: str, *, reference: str, note: str) -> dict:
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant_id))
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if session.scalar(select(SaasPaymentEvidence).where(
        SaasPaymentEvidence.external_reference == reference
    )):
        raise HTTPException(409, "External payment reference already recorded")
    session.add(SaasPaymentEvidence(
        tenant_id=tenant_id, external_reference=reference, operator_note=note,
    ))
    tenant.billing_state = "verified_manual_payment"
    audit(session, tenant_id, "payment_manual_attestation",
          detail="External reference attested by internal operator, not online payment")
    session.commit()
    return {"tenant_id": tenant_id, "billing_state": tenant.billing_state,
            "manual_verification_only": True, "payment_provider_called": False}
