"""APR-05 locally gated SaaS APIs: never share the operator Basic credentials.

The separate Bearer boundary is intentionally active only if
AI_CORP_SAAS_FOUNDATION_ENABLED is explicitly true.
"""
from __future__ import annotations

import base64
import binascii
import hmac
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.modules.customer_onboarding.router import (
    OnboardingProfile,
    TenderScreenRequest,
    download_company_document,
    inspect_onboarding,
    personalized_screening,
    personalized_uploaded_run_screening,
    revise_profile,
    upload_company_document,
)
from src.modules.saas_foundation.models import (
    SaasAccessToken,
    SaasMember,
    SaasRun,
    SaasTenant,
)
from src.modules.saas_foundation.service import (
    PACKAGES,
    PRIVACY_VERSION,
    TERMS_VERSION,
    TenantPrincipal,
    accept_terms,
    audit,
    charge,
    create_tenant,
    digest,
    issue_invitation,
    legal_required,
    now_utc,
    overview,
    owned_run,
    random_secret,
    redeem_invitation,
    refund,
    require_tenant,
    role_required,
    usage_view,
    verify_manual_payment,
)
from src.modules.tender_operator_agent_demo.fast_preanalysis import parse_44fz_reference
from src.modules.tender_operator_agent_demo.procurement_intake_service import (
    create_run_from_eis_docs_archive,
)
from src.modules.tender_operator_agent_demo.schemas import EisDocsArchiveRunRequest
from src.modules.tender_operator_agent_demo.upload_service import (
    analyze_uploaded_demo_run,
    append_files_to_demo_run,
    create_uploaded_demo_run,
    get_uploaded_demo_report,
    get_uploaded_demo_run,
)
from src.shared.api.dependencies import DBSession
from src.shared.config.settings import get_settings

router = APIRouter(tags=["saas-foundation"])


def _enabled() -> None:
    if not get_settings().saas_foundation_enabled:
        raise HTTPException(404, "SaaS foundation is disabled")


def _operator(request: Request) -> None:
    _enabled()
    settings = get_settings()
    username, password = settings.pilot_auth_credentials()
    if not settings.pilot_auth_is_enabled() or not username or not password:
        raise HTTPException(503, "Operator Basic authorization is not configured")
    raw = request.headers.get("Authorization", "")
    scheme, _, encoded = raw.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        raise HTTPException(401, "Operator credentials required")
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(401, "Operator credentials required") from exc
    supplied_user, separator, supplied_password = decoded.partition(":")
    if not separator or not hmac.compare_digest(supplied_user, username) or not hmac.compare_digest(supplied_password, password):
        raise HTTPException(401, "Operator credentials required")


def _principal(
    session: DBSession,
    authorization: Annotated[str | None, Header()] = None,
) -> TenantPrincipal:
    _enabled()
    if not authorization:
        raise HTTPException(401, "Tenant Bearer authorization required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Tenant Bearer authorization required")
    return require_tenant(session, token)


Member = Annotated[TenantPrincipal, Depends(_principal)]
Operator = Annotated[None, Depends(_operator)]


class TenantBootstrap(BaseModel):
    customer_id: str = Field(min_length=4, max_length=64)
    plan_code: Literal["pilot", "team"] = "pilot"


class InviteRequest(BaseModel):
    role: Literal["admin", "analyst", "viewer"]
    acquisition_channel: str = Field(default="referral", pattern=r"^[a-z][a-z0-9_-]{0,39}$")


class RedeemRequest(BaseModel):
    invitation_code: str = Field(min_length=20, max_length=160)
    display_name: str = Field(min_length=2, max_length=160)


class LegalAck(BaseModel):
    terms_version: str
    privacy_version: str
    confirm_read: Literal[True]


class VerifyPaymentRequest(BaseModel):
    external_reference: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9:_./-]+$")
    operator_note: str = Field(min_length=20, max_length=512)
    personally_verified_against_external_statement: Literal[True]


class SaasEisImportRequest(BaseModel):
    reference: str = Field(min_length=19, max_length=512)


class CreateRunRequest(BaseModel):
    tender_title: str
    tender_category: str


@router.get("/api/saas/packages")
def packages() -> dict:
    _enabled()
    return {
        "contract_version": "apr05-package-v1",
        "packages": PACKAGES,
        "pricing_status": "draft_requires_owner_approval",
        "payment_provider_connected": False,
        "online_checkout_enabled": False,
        "public_offer_published": False,
        "human_control_required": True,
    }


@router.post("/api/operator/saas/tenants", status_code=201)
def operator_bootstrap(payload: TenantBootstrap, request: Request, session: DBSession) -> dict:
    _operator(request)
    return create_tenant(session, customer_id=payload.customer_id, plan_code=payload.plan_code)


@router.post("/api/operator/saas/tenants/{tenant_id}/verify-manual-payment")
def operator_manual_verification(tenant_id: str, payload: VerifyPaymentRequest, request: Request, session: DBSession) -> dict:
    _operator(request)
    return verify_manual_payment(
        session, tenant_id, reference=payload.external_reference, note=payload.operator_note,
    )


@router.post("/api/operator/saas/tenants/{tenant_id}/suspend")
def operator_suspend(tenant_id: str, request: Request, session: DBSession) -> dict:
    _operator(request)
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant_id))
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tenant.lifecycle = "suspended"
    audit(session, tenant_id, "tenant_suspended")
    session.commit()
    return {"tenant_id": tenant_id, "lifecycle": "suspended"}


@router.post("/api/saas/invitations/redeem", status_code=201)
def redeem(payload: RedeemRequest, session: DBSession) -> dict:
    _enabled()
    return redeem_invitation(session, payload.invitation_code, payload.display_name)


@router.get("/api/saas/me")
def me(principal: Member, session: DBSession) -> dict:
    return overview(session, principal)


@router.get("/api/saas/legal")
def legal(principal: Member) -> dict:
    return {
        "terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION,
        "scope": "internal controlled pilot, not approved public offer or qualified electronic signature",
        "human_control_required": True,
        "automated_bid_submission": False, "payment_provider_connected": False,
        "require_explicit_acknowledgement": True,
        "tenant_id": principal.tenant_id,
    }


@router.post("/api/saas/legal/accept")
def accept(payload: LegalAck, principal: Member, session: DBSession) -> dict:
    return accept_terms(session, principal, terms=payload.terms_version, privacy=payload.privacy_version)


@router.post("/api/saas/logout")
def logout(principal: Member, session: DBSession) -> dict:
    token = session.scalar(select(SaasAccessToken).where(SaasAccessToken.id == principal.token_id))
    if token:
        token.revoked_at = now_utc()
        audit(session, principal.tenant_id, "access_revoked", principal.member_id)
        session.commit()
    return {"revoked": True}


@router.post("/api/saas/token/rotate")
def rotate_token(principal: Member, session: DBSession) -> dict:
    current = session.scalar(select(SaasAccessToken).where(
        SaasAccessToken.id == principal.token_id
    ).with_for_update())
    if not current or current.revoked_at:
        raise HTTPException(401, "Current token has been revoked")
    raw = random_secret("saas")
    expires_at = now_utc() + timedelta(days=14)
    session.add(SaasAccessToken(
        tenant_id=principal.tenant_id, member_id=principal.member_id,
        token_sha256=digest(raw), expires_at=expires_at,
    ))
    current.revoked_at = now_utc()
    audit(session, principal.tenant_id, "token_rotated", principal.member_id)
    session.commit()
    return {"access_token": raw, "token_type": "Bearer", "expires_at": expires_at.isoformat(),
            "show_token_once": True}


@router.get("/api/operator/saas/tenants/{tenant_id}")
def operator_tenant_summary(tenant_id: str, request: Request, session: DBSession) -> dict:
    _operator(request)
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == tenant_id))
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return {"tenant_id": tenant.tenant_id, "customer_id": tenant.customer_id,
            "plan_code": tenant.plan_code, "billing_state": tenant.billing_state,
            "lifecycle": tenant.lifecycle, "trial_ends_at": tenant.trial_ends_at.isoformat(),
            "live_payment_provider": False}


@router.post("/api/saas/invitations")
def invite(payload: InviteRequest, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    return issue_invitation(
        session, principal.tenant_id, role=payload.role,
        acquisition_channel=payload.acquisition_channel, actor_id=principal.member_id,
    )


@router.get("/api/saas/members")
def members(principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    rows = list(session.scalars(select(SaasMember).where(SaasMember.tenant_id == principal.tenant_id)))
    return {"members": [{"member_id": item.id, "name": item.display_name,
                         "role": item.role, "active": item.active} for item in rows]}


@router.post("/api/saas/members/{member_id}/revoke")
def revoke_member(member_id: str, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    row = session.scalar(select(SaasMember).where(
        SaasMember.id == member_id, SaasMember.tenant_id == principal.tenant_id
    ))
    if not row:
        raise HTTPException(404, "Member not found")
    if row.role == "owner" or row.id == principal.member_id:
        raise HTTPException(409, "Owner and self-revocation require controlled recovery")
    row.active = False
    for token in session.scalars(select(SaasAccessToken).where(
        SaasAccessToken.tenant_id == principal.tenant_id,
        SaasAccessToken.member_id == row.id,
    )):
        token.revoked_at = now_utc()
    audit(session, principal.tenant_id, "member_revoked", principal.member_id,
          detail="role access removed")
    session.commit()
    return {"member_id": member_id, "active": False}


@router.get("/api/saas/profile")
def profile(principal: Member, session: DBSession) -> dict:
    legal_required(session, principal)
    return inspect_onboarding(principal.customer_id, session)


@router.put("/api/saas/profile")
def update_profile(payload: OnboardingProfile, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    return revise_profile(principal.customer_id, payload, session)


@router.get("/api/saas/usage")
def usage(principal: Member, session: DBSession) -> dict:
    legal_required(session, principal)
    return usage_view(session, principal)


@router.get("/api/saas/metrics")
def metrics(principal: Member, session: DBSession) -> dict:
    legal_required(session, principal)
    return overview(session, principal)


@router.post("/api/saas/documents", status_code=201)
async def upload_document(
    principal: Member, session: DBSession,
    file: Annotated[UploadFile, File()],
    document_key: str = Form(...), document_type: str = Form(...),
    display_name: str = Form(...), expires_at: str | None = Form(None),
) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    charge(session, principal, "documents")
    try:
        return await upload_company_document(
            principal.customer_id, session, document_key=document_key,
            document_type=document_type, display_name=display_name,
            expires_at=expires_at, file=file,
        )
    except Exception:
        session.rollback()
        refund(session, principal, "documents")
        raise


@router.get("/api/saas/documents/{document_key}/download")
def download_document(document_key: str, principal: Member, session: DBSession):
    legal_required(session, principal)
    return download_company_document(principal.customer_id, document_key, session)


@router.post("/api/saas/screen")
def screen(payload: TenderScreenRequest, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    charge(session, principal, "screens")
    try:
        return personalized_screening(principal.customer_id, payload, session)
    except Exception:
        session.rollback()
        refund(session, principal, "screens")
        raise


@router.post("/api/saas/runs", status_code=201)
async def create_run(
    principal: Member, session: DBSession,
    files: Annotated[list[UploadFile], File()],
    tender_title: str = Form(...), tender_category: str = Form("Не определена"),
    procurement_customer_name: str = Form("Не установлен (требует проверки)"),
) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    if not procurement_customer_name.strip() or len(procurement_customer_name) > 256:
        raise HTTPException(422, "Procurement contracting authority name invalid")
    # The tenant's company is the supplier, not the purchasing authority.
    charge(session, principal, "runs")
    try:
        if not files or len(files) > 16:
            raise HTTPException(413, "Tender document count limit exceeded")
        uploads = []
        total_bytes = 0
        for item in files:
            content = await item.read(12 * 1024 * 1024 + 1)
            total_bytes += len(content)
            if len(content) > 12 * 1024 * 1024 or total_bytes > 40 * 1024 * 1024:
                raise HTTPException(413, "Tender document size limit exceeded")
            uploads.append((
                item.filename or "file.bin",
                item.content_type or "application/octet-stream", content,
            ))
        result = create_uploaded_demo_run(
            tender_title=tender_title, tender_category=tender_category,
            customer_name=procurement_customer_name.strip(),
            notes="APR-05 tenant-bound pilot; procurement customer unverified until cited",
            target_margin_percent=15, logistics_reserve_percent=3,
            risk_reserve_percent=5, payment_delay_days=45, uploads=uploads,
        )
        session.add(SaasRun(tenant_id=principal.tenant_id, run_id=result.run_id,
                            created_by_member_id=principal.member_id))
        audit(session, principal.tenant_id, "run_created", principal.member_id)
        session.commit()
        return {"run_id": result.run_id, "status": result.status,
                "tenant_id": principal.tenant_id, "external_action_allowed": False}
    except Exception:
        session.rollback()
        refund(session, principal, "runs")
        raise


@router.post("/api/saas/runs/from-eis", status_code=201)
def import_eis(payload: SaasEisImportRequest, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    try:
        number = parse_44fz_reference(payload.reference)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    charge(session, principal, "runs")
    try:
        result = create_run_from_eis_docs_archive(
            EisDocsArchiveRunRequest(
                reestr_number=number, law="44fz", subsystem_type="PRIZ",
                method="getDocsByReestrNumber",
                download_archive=True, analyze_after_download=False,
            )
        )
        session.add(SaasRun(
            tenant_id=principal.tenant_id, run_id=result.run_id,
            created_by_member_id=principal.member_id,
        ))
        audit(session, principal.tenant_id, "eis_readonly_run_created", principal.member_id,
              detail=number)
        session.commit()
        return {"run_id": result.run_id, "status": result.status,
                "tenant_id": principal.tenant_id,
                "downloaded_files_count": result.downloaded_files_count,
                "external_action_allowed": False}
    except Exception:
        session.rollback()
        refund(session, principal, "runs")
        raise


@router.post("/api/saas/runs/{run_id}/files")
async def append_owned_files(
    run_id: str, principal: Member, session: DBSession,
    files: Annotated[list[UploadFile], File()],
) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    owned_run(session, principal, run_id)
    charge(session, principal, "documents")
    try:
        if not files or len(files) > 16:
            raise HTTPException(413, "Tender document count limit exceeded")
        uploads = []
        total_bytes = 0
        for item in files:
            content = await item.read(12 * 1024 * 1024 + 1)
            total_bytes += len(content)
            if len(content) > 12 * 1024 * 1024 or total_bytes > 40 * 1024 * 1024:
                raise HTTPException(413, "Tender document size limit exceeded")
            uploads.append((item.filename or "file.bin",
                            item.content_type or "application/octet-stream", content))
        result = append_files_to_demo_run(run_id=run_id, uploads=uploads)
        audit(session, principal.tenant_id, "tenant_run_files_appended", principal.member_id)
        session.commit()
        return {"run_id": run_id, "status": result.status,
                "external_action_allowed": False}
    except Exception:
        session.rollback()
        refund(session, principal, "documents")
        raise


@router.post("/api/saas/runs/{run_id}/analyze")
def analyze(run_id: str, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    owned_run(session, principal, run_id)
    previous = get_uploaded_demo_run(run_id)
    if getattr(previous.status, "value", str(previous.status)) in {
        "completed", "completed_with_warnings", "needs_review",
    }:
        raise HTTPException(409, "Tender run already has a terminal analysis")
    charge(session, principal, "analyses")
    try:
        result = analyze_uploaded_demo_run(run_id)
        audit(session, principal.tenant_id, "tenant_run_analyzed", principal.member_id)
        session.commit()
        return {"run_id": run_id, "status": result.status,
                "external_action_allowed": False, "human_control_required": True}
    except Exception:
        session.rollback()
        refund(session, principal, "analyses")
        raise


@router.get("/api/saas/runs/{run_id}/report")
def report(run_id: str, principal: Member, session: DBSession) -> dict:
    legal_required(session, principal)
    owned_run(session, principal, run_id)
    r = get_uploaded_demo_report(run_id)
    return {
        "run_id": r.run_id, "report_title": r.report_title,
        "recommendation": r.recommendation,
        "manual_checks": r.manual_checks,
        "executive_summary": r.executive_summary,
        "sections": [section.model_dump(mode="json") for section in r.sections],
        "human_control_required": True, "external_action_allowed": False,
    }


@router.post("/api/saas/runs/{run_id}/screen")
def screen_run(run_id: str, principal: Member, session: DBSession) -> dict:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    owned_run(session, principal, run_id)
    charge(session, principal, "screens")
    try:
        return personalized_uploaded_run_screening(principal.customer_id, run_id, session)
    except Exception:
        session.rollback()
        refund(session, principal, "screens")
        raise


@router.get("/saas", response_class=HTMLResponse)
def saas_page() -> str:
    _enabled()
    from src.modules.saas_foundation.ui import render_saas_html
    return render_saas_html()
