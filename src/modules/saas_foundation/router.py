"""APR-05 locally gated SaaS APIs: never share the operator Basic credentials.

The separate Bearer boundary is intentionally active only if
AI_CORP_SAAS_FOUNDATION_ENABLED is explicitly true.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
from datetime import datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from src.modules.company_profile_store.qualification_decision import (
    QualificationAwareDecisionRequest,
    QualificationAwareDecisionResponse,
    build_qualification_aware_decision,
)
from src.modules.company_profile_store.qualification_references import (
    REFERENCE_FACT_KEY,
    CompletedContractReferenceSnapshot,
    QualificationAssessment,
    QualificationCriterion,
    assess_company_qualification,
)
from src.modules.company_profile_store.qualification_run_service import (
    assess_owned_run_qualification,
)
from src.modules.company_profile_store.schemas import AppendCompanyProfileFactRequest
from src.modules.company_profile_store.service import (
    append_company_profile_fact,
    get_company_profile_fact_history,
)
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
from src.modules.saas_foundation import (
    commercial_attachment_service,
    commercial_capture,
    commercial_requirement_review,
    company_actual_costs,
    company_actual_evidence,
    company_actual_samples,
    company_case_evidence,
    company_cost_evidence,
    company_cost_norms,
    company_discovery,
    company_historical_comparables,
    company_lifecycle,
    company_lifecycle_artifacts,
    company_portfolio,
    company_price_scenarios,
    company_readiness,
    company_schedule,
)
from src.modules.saas_foundation.commercial_attachment_bytes import MAX_ATTACHMENT_BYTES
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
    qualification = (
        assess_owned_run_qualification(
            session, run_id=run_id, customer_id=principal.customer_id,
            as_of=datetime.now(ZoneInfo("Europe/Moscow")).date(),
        )
        if principal.role in {"owner", "admin", "analyst"}
        else {
            "source_status": "REFERENCE_ACCESS_RESTRICTED",
            "competitive_recommendation": "NOT_ASSESSED",
            "human_gold": False,
            "external_action_allowed": False,
        }
    )
    return {
        "qualification": qualification,
        "run_id": r.run_id, "report_title": r.report_title,
        "recommendation": r.recommendation,
        "manual_checks": r.manual_checks,
        "executive_summary": r.executive_summary,
        "sections": [section.model_dump(mode="json") for section in r.sections],
        "human_control_required": True, "external_action_allowed": False,
    }


@router.get("/api/saas/runs/{run_id}/qualification")
def owned_run_qualification(run_id: str, principal: Member, session: DBSession) -> dict:
    """Zero input scoring weights/UID; supplier tenant from authenticated session."""
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    owned_run(session, principal, run_id)
    return assess_owned_run_qualification(
        session, run_id=run_id, customer_id=principal.customer_id,
        as_of=datetime.now(ZoneInfo("Europe/Moscow")).date(),
    )


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


class OwnerReferencesRequest(BaseModel):
    snapshot: CompletedContractReferenceSnapshot
    source_ref: str = Field(min_length=1, max_length=512)
    expected_version: int = Field(ge=0)
    expires_at: datetime | None = None


@router.get("/api/saas/qualification/references")
def saas_company_references(principal: Member, session: DBSession) -> dict:
    """Current private reference-list version for bearer-authenticated owner tenant."""
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    from src.shared.errors import NotFoundError

    try:
        history = get_company_profile_fact_history(
            session, customer_id=principal.customer_id, fact_key=REFERENCE_FACT_KEY,
        )
    except NotFoundError:
        return {"state": "UNKNOWN", "fact_version": None, "snapshot": None}
    record = history[-1]
    return {
        "state": "STORED",
        "fact_version": record.version_no,
        "source_type": record.source_type,
        "source_ref": record.source_ref,
        "expires_at": record.expires_at,
        "snapshot": record.value_json,
    }


@router.post("/api/saas/qualification/references", status_code=201)
def saas_record_company_references(
    payload: OwnerReferencesRequest, principal: Member, session: DBSession,
) -> dict:
    """An authorized owner/admin appends a new immutable company fact version."""
    role_required(principal, "owner", "admin")
    legal_required(session, principal)
    from src.shared.errors import NotFoundError

    try:
        history = get_company_profile_fact_history(
            session, customer_id=principal.customer_id, fact_key=REFERENCE_FACT_KEY,
        )
        latest = history[-1].version_no
    except NotFoundError:
        latest = 0
    if payload.expected_version != latest:
        raise HTTPException(
            409, "Reference list was updated by another editor; reload before saving",
        )
    try:
        record = append_company_profile_fact(
            session,
            customer_id=principal.customer_id,
            fact_key=REFERENCE_FACT_KEY,
            payload=AppendCompanyProfileFactRequest(
                fact_group="EXPERIENCE",
                value=payload.snapshot.model_dump(mode="json"),
                source_type="CUSTOMER_PROVIDED",
                source_ref=payload.source_ref,
                expires_at=payload.expires_at,
            ),
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            409, "Concurrent reference-list version write; reload before saving",
        ) from exc
    return {
        "customer_id": principal.customer_id,
        "fact_version": record.version_no,
        "fact_id": record.id,
        "source_type": record.source_type,
        "human_gold": False,
        "external_action_allowed": False,
    }


@router.post("/api/saas/qualification/assess", response_model=QualificationAssessment)
def saas_qualify_company(
    payload: QualificationCriterion, principal: Member, session: DBSession,
) -> QualificationAssessment:
    """Tenant identity comes only from authenticated Bearer principal."""
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    return assess_company_qualification(
        session, customer_id=principal.customer_id, criterion=payload,
    )


@router.post(
    "/api/saas/qualification/decision-core",
    response_model=QualificationAwareDecisionResponse,
)
def saas_qualification_decision(
    payload: QualificationAwareDecisionRequest, principal: Member, session: DBSession,
) -> QualificationAwareDecisionResponse:
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    return build_qualification_aware_decision(
        session, customer_id=principal.customer_id, request=payload,
    )


@router.get("/saas", response_class=HTMLResponse)
def saas_page() -> str:
    _enabled()
    from src.modules.saas_foundation.ui import render_saas_html
    return render_saas_html()


@router.post("/api/saas/company-portfolio/cases", status_code=201, response_model=company_portfolio.CompanyCaseView)
def save_company_case(payload: company_portfolio.SaveCompanyCase, principal: Member, session: DBSession) -> dict:
    return company_portfolio.save_case(session, principal, payload)


@router.get("/api/saas/company-portfolio/cases", response_model=company_portfolio.CompanyPortfolioPage)
def list_company_cases(principal: Member, session: DBSession, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)) -> dict:
    return company_portfolio.list_cases(session, principal, offset=offset, limit=limit)


@router.get("/api/saas/company-portfolio/cases/{case_id}", response_model=company_portfolio.CompanyCaseView)
def read_company_case(case_id: str, principal: Member, session: DBSession) -> dict:
    return company_portfolio.get_case(session, principal, case_id)


@router.get("/api/saas/company-portfolio/cases/{case_id}/decisions", response_model=company_portfolio.CompanyDecisionPage)
def read_company_case_decisions(case_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)) -> dict:
    return company_portfolio.decision_history(session, principal, case_id, offset=offset, limit=limit)


@router.post("/api/saas/company-portfolio/cases/{case_id}/decisions", response_model=company_portfolio.CompanyDecisionView)
def write_company_case_decision(case_id: str, payload: company_portfolio.CompanyDecisionInput, principal: Member, session: DBSession) -> dict:
    return company_portfolio.record_decision(session, principal, case_id, payload)


@router.get("/api/saas/company-portfolio/search-context", response_model=company_case_evidence.SearchContext)
def company_search_context(principal: Member, session: DBSession):
    return company_case_evidence.search_context(session, principal)


@router.post("/api/saas/company-portfolio/cases/{case_id}/evidence", status_code=201)
def bind_company_evidence(case_id: str, payload: company_case_evidence.BindCaseEvidence, principal: Member, session: DBSession) -> dict:
    return company_case_evidence.bind_evidence(session, principal, case_id, payload)


@router.get("/api/saas/company-portfolio/cases/{case_id}/evidence")
def list_company_evidence(case_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)) -> dict:
    return company_case_evidence.list_evidence(session, principal, case_id, offset=offset, limit=limit)


@router.get("/api/saas/company-portfolio/cases/{case_id}/evidence/{binding_id}")
def read_company_evidence(case_id: str, binding_id: str, principal: Member, session: DBSession) -> dict:
    return company_case_evidence.read_evidence(session, principal, case_id, binding_id)



def _company_discovery_enabled():
    if not get_settings().saas_company_discovery_enabled:
        raise HTTPException(404, "Company discovery is disabled")


@router.post("/api/saas/company-portfolio/discovery/runs", status_code=201)
def plan_company_discovery(payload: company_discovery.StartCompanyDiscovery, principal: Member, session: DBSession) -> dict:
    _company_discovery_enabled()
    return company_discovery.create_run(session, principal, payload)


@router.get("/api/saas/company-portfolio/discovery/latest")
def latest_company_discovery(principal: Member, session: DBSession) -> dict:
    return {"enabled": get_settings().saas_company_discovery_enabled, "commercial_indexes": list(company_discovery.INDEXES), "run": company_discovery.latest_run(session, principal)}


@router.get("/api/saas/company-portfolio/discovery/runs/{run_id}")
def read_company_discovery(run_id: str, principal: Member, session: DBSession) -> dict:
    return company_discovery.read_run(session, principal, run_id)


@router.post("/api/saas/company-portfolio/discovery/runs/{run_id}/step")
def advance_company_discovery(run_id: str, payload: company_discovery.AdvanceCompanyDiscovery, principal: Member, session: DBSession) -> dict:
    _company_discovery_enabled()
    return company_discovery.advance_run(session, principal, run_id, payload)


@router.post("/api/saas/company-portfolio/commercial-cases", status_code=201, response_model=company_portfolio.CompanyCaseView)
def save_company_commercial_case(payload: company_portfolio.SaveCommercialCase, principal: Member, session: DBSession) -> dict:
    return company_portfolio.save_commercial_case(session, principal, payload)


@router.get("/api/saas/company-portfolio/discovery/schedule")
def read_company_schedule(principal: Member, session: DBSession) -> dict:
    return company_schedule.read_schedule(session, principal, execution_enabled=company_schedule.execution_enabled(get_settings()))


@router.put("/api/saas/company-portfolio/discovery/schedule")
def update_company_schedule(payload: company_schedule.ScheduleInput, principal: Member, session: DBSession) -> dict:
    return company_schedule.update_schedule(session, principal, payload, execution_enabled=company_schedule.execution_enabled(get_settings()))


@router.post("/api/saas/company-portfolio/cases/{case_id}/commercial-captures", status_code=201)
def capture_company_commercial_card(case_id: str, payload: commercial_capture.CaptureRequest, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_commercial_capture_enabled:
        raise HTTPException(404, "Commercial capture disabled")
    return commercial_capture.capture(session, principal, case_id, payload)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures")
def list_company_commercial_captures(case_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=20)) -> dict:
    return {**commercial_capture.list_captures(session, principal, case_id, offset=offset, limit=limit),
            "capture_enabled": get_settings().saas_commercial_capture_enabled}


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}")
def recheck_company_commercial_capture(case_id: str, attempt_id: str, principal: Member, session: DBSession, previous_attempt_id: str | None = Query(None, max_length=64)) -> dict:
    if previous_attempt_id is not None:
        result = commercial_capture.compare_captures(session, principal, case_id, attempt_id, previous_attempt_id)
    else:
        result = commercial_capture.recheck(session, principal, case_id, attempt_id)
    return {**result, "attachment_intake_enabled": get_settings().saas_commercial_attachment_intake_enabled,
            "text_projection_enabled": get_settings().saas_commercial_text_projection_enabled,
            "requirement_review_enabled": get_settings().saas_commercial_requirement_review_enabled}


@router.post("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}", status_code=201)
async def save_company_commercial_attachment(case_id: str, attempt_id: str, candidate_id: str, request: Request, principal: Member, session: DBSession, confirm_user_supplied: bool = Query(False)) -> dict:
    if not get_settings().saas_commercial_attachment_intake_enabled:
        raise HTTPException(404, "Commercial attachment intake disabled")
    role_required(principal, "owner", "admin", "analyst")
    legal_required(session, principal)
    if not confirm_user_supplied:
        raise HTTPException(422, "Confirm user-supplied, unverified origin")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Encoded uploads unsupported")
    length = request.headers.get("content-length")
    if length is not None and (not length.isascii() or not length.isdecimal() or len(length) > 10):
        raise HTTPException(400, "Invalid upload length")
    if length is not None and int(length) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachment size limit exceeded")
    # Avoid holding the initial auth transaction across untrusted upload I/O.
    session.rollback()
    raw = bytearray()
    try:
        async with asyncio.timeout(20):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(413, "Attachment size limit exceeded")
                raw.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(408, "Attachment upload timeout") from exc
    return await run_in_threadpool(commercial_attachment_service.save, session, principal, case_id, attempt_id, candidate_id, bytes(raw))


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments")
def list_company_commercial_attachments(case_id: str, attempt_id: str, principal: Member, session: DBSession) -> dict:
    return commercial_attachment_service.list_evidence(session, principal, case_id, attempt_id)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}")
def read_company_commercial_attachment(case_id: str, attempt_id: str, candidate_id: str, principal: Member, session: DBSession, previous_attempt_id: str | None = Query(None, max_length=64)) -> dict:
    return commercial_attachment_service.read(session, principal, case_id, attempt_id, candidate_id, previous_attempt_id)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}/text-evidence")
def read_company_commercial_text_evidence(case_id: str, attempt_id: str, candidate_id: str, principal: Member, session: DBSession) -> dict:
    settings = get_settings()
    if not settings.saas_commercial_text_projection_enabled:
        raise HTTPException(404, "Commercial text projection disabled")
    return commercial_attachment_service.text_evidence(session, principal, case_id, attempt_id, candidate_id,
        pdf_enabled=settings.saas_commercial_pdf_projection_enabled)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}/requirements")
def commercial_requirement_matrix(case_id: str, attempt_id: str, candidate_id: str, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_commercial_requirement_review_enabled:
        raise HTTPException(404, "Requirement review disabled")
    return commercial_requirement_review.matrix(session, principal, case_id, attempt_id, candidate_id)


@router.post("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}/requirements", status_code=201)
def commercial_requirement_submit(case_id: str, attempt_id: str, candidate_id: str, payload: commercial_requirement_review.ReviewInput, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_commercial_requirement_review_enabled:
        raise HTTPException(404, "Requirement review disabled")
    return commercial_requirement_review.submit(session, principal, case_id, attempt_id, candidate_id, payload)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/attachments/{candidate_id}/requirements/{fragment_key}")
def commercial_requirement_history(case_id: str, attempt_id: str, candidate_id: str, fragment_key: str, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_commercial_requirement_review_enabled:
        raise HTTPException(404, "Requirement review disabled")
    return commercial_requirement_review.history(session, principal, case_id, attempt_id, candidate_id, fragment_key)


@router.get("/api/saas/company-portfolio/cases/{case_id}/commercial-captures/{attempt_id}/requirement-matrix")
def commercial_case_requirement_matrix(case_id: str, attempt_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0, le=20), limit: int = Query(3, ge=1, le=3)) -> dict:
    if not get_settings().saas_commercial_requirement_review_enabled:
        raise HTTPException(404, "Requirement review disabled")
    return commercial_requirement_review.case_matrix(session, principal, case_id, attempt_id, offset=offset, limit=limit)


@router.get("/api/saas/company-portfolio/manager-inbox")
def company_manager_inbox(principal: Member, session: DBSession, view: company_portfolio.InboxFilter = "attention", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)) -> dict:
    return company_portfolio.manager_inbox(session, principal, view=view, offset=offset, limit=limit)


@router.get("/api/saas/company-portfolio/cases/{case_id}/lifecycle")
def company_lifecycle_state(case_id: str, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_company_lifecycle_enabled:
        raise HTTPException(404, "Company lifecycle disabled")
    return company_lifecycle.state(session, principal, case_id)


@router.post("/api/saas/company-portfolio/cases/{case_id}/lifecycle", status_code=201)
def company_lifecycle_record(case_id: str, payload: company_lifecycle.LifecycleInput, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_company_lifecycle_enabled:
        raise HTTPException(404, "Company lifecycle disabled")
    return company_lifecycle.record(session, principal, case_id, payload, require_commercial_readiness=get_settings().saas_company_commercial_readiness_required)


@router.get("/api/saas/company-portfolio/cases/{case_id}/lifecycle/history")
def company_lifecycle_history(case_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0, le=50), limit: int = Query(50, ge=1, le=50)) -> dict:
    if not get_settings().saas_company_lifecycle_enabled:
        raise HTTPException(404, "Company lifecycle disabled")
    return company_lifecycle.history(session, principal, case_id, offset, limit)


@router.get("/api/saas/company-portfolio/lifecycle-metrics")
def company_lifecycle_metrics(principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_company_lifecycle_enabled:
        raise HTTPException(404, "Company lifecycle disabled")
    return company_lifecycle.metrics(session, principal)


@router.get("/api/saas/company-portfolio/cases/{case_id}/readiness-evidence")
def company_readiness_state(case_id: str, principal: Member, session: DBSession) -> dict:
    settings=get_settings()
    if not (settings.saas_company_lifecycle_enabled and settings.saas_company_readiness_evidence_enabled):
        raise HTTPException(404, "Readiness evidence disabled")
    return company_readiness.state(session, principal, case_id)


@router.post("/api/saas/company-portfolio/cases/{case_id}/readiness-evidence", status_code=201)
def company_readiness_bind(case_id: str, payload: company_readiness.BindInput, principal: Member, session: DBSession) -> dict:
    settings=get_settings()
    if not (settings.saas_company_lifecycle_enabled and settings.saas_company_readiness_evidence_enabled):
        raise HTTPException(404, "Readiness evidence disabled")
    return company_readiness.bind(session, principal, case_id, payload)


async def _bounded_evidence_upload(request: Request, session: DBSession) -> bytes:
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Encoded uploads unsupported")
    length=request.headers.get("content-length")
    if length is not None and (not length.isascii() or not length.isdecimal() or len(length)>10):
        raise HTTPException(400, "Invalid upload length")
    if length is not None and int(length)>MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachment size limit exceeded")
    session.rollback()
    raw=bytearray()
    try:
        async with asyncio.timeout(20):
            async for chunk in request.stream():
                if len(raw)+len(chunk)>MAX_ATTACHMENT_BYTES:
                    raise HTTPException(413, "Attachment size limit exceeded")
                raw.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(408, "Attachment upload timeout") from exc
    return bytes(raw)


@router.post("/api/saas/company-portfolio/cases/{case_id}/lifecycle/{event_id}/artifact", status_code=201)
async def upload_lifecycle_artifact(case_id: str, event_id: str, request: Request, principal: Member, session: DBSession, format_hint: company_lifecycle_artifacts.ArtifactFormat, confirm_user_supplied: bool = Query(False)) -> dict:
    settings=get_settings()
    if not (settings.saas_company_lifecycle_enabled and settings.saas_company_lifecycle_artifacts_enabled):
        raise HTTPException(404, "Lifecycle artifacts disabled")
    role_required(principal, "owner", "admin")
    company_lifecycle_artifacts._event(session,principal,case_id,event_id)
    if not confirm_user_supplied:
        raise HTTPException(422, "Confirm user-supplied unverified origin")
    raw = await _bounded_evidence_upload(request, session)
    return await run_in_threadpool(company_lifecycle_artifacts.save, session, principal, case_id, event_id, bytes(raw), format_hint)


@router.get("/api/saas/company-portfolio/cases/{case_id}/lifecycle/{event_id}/artifact")
def read_lifecycle_artifact(case_id: str, event_id: str, principal: Member, session: DBSession) -> dict:
    settings=get_settings()
    if not (settings.saas_company_lifecycle_enabled and settings.saas_company_lifecycle_artifacts_enabled):
        raise HTTPException(404, "Lifecycle artifacts disabled")
    return company_lifecycle_artifacts.read(session, principal, case_id, event_id)


@router.get("/api/saas/company-portfolio/cases/{case_id}/lifecycle/{event_id}/artifact/download")
def download_lifecycle_artifact(case_id: str, event_id: str, principal: Member, session: DBSession):
    settings=get_settings()
    if not (settings.saas_company_lifecycle_enabled and settings.saas_company_lifecycle_artifacts_enabled):
        raise HTTPException(404, "Lifecycle artifacts disabled")
    raw, format_hint, sha=company_lifecycle_artifacts.download(session, principal, case_id, event_id)
    return Response(content=raw, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="lifecycle-{sha[:16]}.{format_hint}"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "X-Artifact-SHA256": sha})


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/preview")
def company_price_preview(case_id: str, payload: company_price_scenarios.ScenarioInput, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_company_price_scenarios_enabled:
        raise HTTPException(404, "Price scenarios disabled")
    return company_price_scenarios.preview(session, principal, case_id, payload)


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios")
def company_price_history(case_id: str, principal: Member, session: DBSession, offset: int = Query(0, ge=0, le=30), limit: int = Query(10, ge=1, le=30)) -> dict:
    if not get_settings().saas_company_price_scenarios_enabled:
        raise HTTPException(404, "Price scenarios disabled")
    return company_price_scenarios.history(session, principal, case_id, offset, limit)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios", status_code=201)
def company_price_save(case_id: str, payload: company_price_scenarios.SaveInput, principal: Member, session: DBSession) -> dict:
    if not get_settings().saas_company_price_scenarios_enabled:
        raise HTTPException(404, "Price scenarios disabled")
    return company_price_scenarios.save(session, principal, case_id, payload)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/itemized/preview")
def company_price_itemized_preview(case_id: str, payload: company_price_scenarios.ItemizedInput, principal: Member, session: DBSession) -> dict:
    settings=get_settings()
    if not (settings.saas_company_price_scenarios_enabled and settings.saas_company_price_itemized_enabled):
        raise HTTPException(404, "Itemized price scenarios disabled")
    if company_price_scenarios.has_norm_bindings(payload):
        _cost_norms_enabled()
        if not settings.saas_company_cost_norm_binding_enabled:raise HTTPException(404,"Norm estimate binding disabled")
    return company_price_scenarios.preview_itemized(session, principal, case_id, payload)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/itemized", status_code=201)
def company_price_itemized_save(case_id: str, payload: company_price_scenarios.ItemizedSaveInput, principal: Member, session: DBSession) -> dict:
    settings=get_settings()
    if not (settings.saas_company_price_scenarios_enabled and settings.saas_company_price_itemized_enabled):
        raise HTTPException(404, "Itemized price scenarios disabled")
    if company_price_scenarios.has_norm_bindings(payload.estimate):
        _cost_norms_enabled()
        if not settings.saas_company_cost_norm_binding_enabled:raise HTTPException(404,"Norm estimate binding disabled")
    return company_price_scenarios.save_itemized(session,principal,case_id,payload)


# Evidence is a user-supplied copy, not verification of the price, payment or signature.
def _cost_evidence_enabled():
    settings=get_settings()
    if not (settings.saas_company_price_scenarios_enabled and settings.saas_company_price_itemized_enabled and settings.saas_company_cost_evidence_enabled):
        raise HTTPException(404, "Cost evidence disabled")


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/lines/{ordinal}/evidence")
def read_cost_evidence(case_id: str, scenario_id: str, ordinal: int, principal: Member, session: DBSession) -> dict:
    _cost_evidence_enabled()
    return company_cost_evidence.read(session,principal,case_id,scenario_id,ordinal)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/lines/{ordinal}/evidence", status_code=201)
async def upload_cost_evidence(case_id: str, scenario_id: str, ordinal: int, request: Request, principal: Member, session: DBSession, format_hint: company_cost_evidence.FormatHint, document_kind: company_cost_evidence.DocumentKind, line_sha256: Annotated[str,Query(pattern=r"^[0-9a-f]{64}$")], confirm_user_supplied: bool = Query(False)) -> dict:
    _cost_evidence_enabled()
    role_required(principal,"owner","admin")
    _,_,digest=company_cost_evidence._line(session,principal,case_id,scenario_id,ordinal)
    if digest!=line_sha256:
        raise HTTPException(409,"Estimate line binding changed; refresh")
    if not confirm_user_supplied:
        raise HTTPException(422,"Confirm user-supplied unverified origin")
    raw=await _bounded_evidence_upload(request,session)
    return await run_in_threadpool(company_cost_evidence.save,session,principal,case_id,scenario_id,ordinal,raw,format_hint,document_kind,line_sha256)


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/lines/{ordinal}/evidence/download")
def download_cost_evidence(case_id: str, scenario_id: str, ordinal: int, principal: Member, session: DBSession):
    _cost_evidence_enabled()
    raw,format_hint,sha=company_cost_evidence.download(session,principal,case_id,scenario_id,ordinal)
    return Response(content=raw,media_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="cost-{sha[:16]}.{format_hint}"',"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","X-Artifact-SHA256":sha})


def _actual_costs_enabled():
    settings=get_settings()
    if not (settings.saas_company_price_scenarios_enabled and settings.saas_company_price_itemized_enabled and settings.saas_company_actual_costs_enabled):
        raise HTTPException(404,"Actual cost snapshots disabled")


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs")
def actual_cost_history(case_id: str, scenario_id: str, principal: Member, session: DBSession, offset: int = Query(0,ge=0,le=30), limit: int = Query(5,ge=1,le=10)) -> dict:
    _actual_costs_enabled()
    return company_actual_costs.history(session,principal,case_id,scenario_id,offset,limit)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs/preview")
def actual_cost_preview(case_id: str, scenario_id: str, payload: company_actual_costs.SnapshotInput, principal: Member, session: DBSession) -> dict:
    _actual_costs_enabled()
    return company_actual_costs.preview(session,principal,case_id,scenario_id,payload)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs",status_code=201)
def actual_cost_save(case_id: str, scenario_id: str, payload: company_actual_costs.SaveInput, principal: Member, session: DBSession) -> dict:
    _actual_costs_enabled()
    return company_actual_costs.save(session,principal,case_id,scenario_id,payload)


def _actual_evidence_enabled():
    _actual_costs_enabled()
    if not get_settings().saas_company_actual_evidence_enabled:
        raise HTTPException(404,"Actual cost evidence disabled")


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs/{snapshot_id}/rows/{row_kind}/{ordinal}/evidence")
def read_actual_evidence(case_id: str, scenario_id: str, snapshot_id: str, row_kind: company_actual_evidence.RowKind, ordinal: int, principal: Member, session: DBSession) -> dict:
    _actual_evidence_enabled()
    return company_actual_evidence.read(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal)


@router.post("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs/{snapshot_id}/rows/{row_kind}/{ordinal}/evidence",status_code=201)
async def upload_actual_evidence(case_id: str, scenario_id: str, snapshot_id: str, row_kind: company_actual_evidence.RowKind, ordinal: int, request: Request, principal: Member, session: DBSession, format_hint: company_cost_evidence.FormatHint, document_kind: company_actual_evidence.DocumentKind, line_sha256: Annotated[str,Query(pattern=r"^[0-9a-f]{64}$")], confirm_user_supplied: bool=Query(False)) -> dict:
    _actual_evidence_enabled()
    role_required(principal,"owner","admin")
    scope=company_actual_evidence.target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal)
    if scope['line_sha256']!=line_sha256:
        raise HTTPException(409,"Actual row binding changed; refresh")
    if not confirm_user_supplied:
        raise HTTPException(422,"Confirm user-supplied unverified origin")
    raw=await _bounded_evidence_upload(request,session)
    return await run_in_threadpool(company_actual_evidence.save,session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal,raw,format_hint,document_kind,line_sha256)


@router.get("/api/saas/company-portfolio/cases/{case_id}/price-scenarios/{scenario_id}/actual-costs/{snapshot_id}/rows/{row_kind}/{ordinal}/evidence/download")
def download_actual_evidence(case_id: str, scenario_id: str, snapshot_id: str, row_kind: company_actual_evidence.RowKind, ordinal: int, principal: Member, session: DBSession):
    _actual_evidence_enabled()
    raw,format_hint,sha=company_actual_evidence.download(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal)
    return Response(content=raw,media_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="actual-{sha[:16]}.{format_hint}"',"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","X-Artifact-SHA256":sha})


@router.post("/api/saas/company-portfolio/actual-samples/preview")
def actual_sample_preview(payload: company_actual_samples.PreviewInput, principal: Member, session: DBSession) -> dict:
    _actual_costs_enabled()
    if not get_settings().saas_company_actual_samples_enabled:
        raise HTTPException(404,"Actual sample preview disabled")
    return company_actual_samples.preview(session,principal,payload)

def _cost_norms_enabled():
    _actual_costs_enabled()
    settings=get_settings()
    if not (settings.saas_company_actual_samples_enabled and settings.saas_company_cost_norms_enabled):
        raise HTTPException(404,"Corporate cost norms disabled")


@router.post("/api/saas/company-portfolio/cost-norms/preview")
def cost_norm_preview(payload: company_cost_norms.Proposal, principal: Member, session: DBSession) -> dict:
    _cost_norms_enabled()
    return company_cost_norms.preview(session,principal,payload)


@router.post("/api/saas/company-portfolio/cost-norms",status_code=201)
def cost_norm_approve(payload: company_cost_norms.Approval, principal: Member, session: DBSession) -> dict:
    _cost_norms_enabled()
    return company_cost_norms.approve(session,principal,payload)


@router.get("/api/saas/company-portfolio/cost-norms")
def cost_norm_catalog(principal: Member, session: DBSession, offset: int=Query(0,ge=0,le=500), limit: int=Query(10,ge=1,le=20)) -> dict:
    _cost_norms_enabled()
    return company_cost_norms.catalog(session,principal,offset,limit)


@router.get("/api/saas/company-portfolio/cost-norms/{norm_key}")
def cost_norm_history(norm_key: company_actual_costs.Digest, principal: Member, session: DBSession, offset: int=Query(0,ge=0,le=100), limit: int=Query(10,ge=1,le=20)) -> dict:
    _cost_norms_enabled()
    return company_cost_norms.history(session,principal,norm_key,offset,limit)


@router.post("/api/saas/company-portfolio/cost-norms/{norm_key}/withdraw",status_code=201)
def cost_norm_withdraw(norm_key: company_actual_costs.Digest, payload: company_cost_norms.Withdrawal, principal: Member, session: DBSession) -> dict:
    _cost_norms_enabled()
    return company_cost_norms.withdraw(session,principal,norm_key,payload)

def _historical_comparables_enabled():
    settings=get_settings()
    if not (settings.saas_company_price_scenarios_enabled and settings.saas_company_historical_comparables_enabled):
        raise HTTPException(404,"Historical comparable evidence disabled")


@router.get("/api/saas/company-portfolio/cases/{case_id}/historical-comparables")
def historical_comparable_catalog(case_id: str, principal: Member, session: DBSession) -> dict:
    _historical_comparables_enabled()
    return company_historical_comparables.catalog(session,principal,case_id)


@router.post("/api/saas/company-portfolio/cases/{case_id}/historical-comparables/preview")
def historical_comparable_preview(case_id: str, payload: company_historical_comparables.Selection, principal: Member, session: DBSession) -> dict:
    _historical_comparables_enabled()
    return company_historical_comparables.preview(session,principal,case_id,payload)

@router.get("/api/saas/company-portfolio/cases/{case_id}/reviewed-contract-registry")
def reviewed_contract_registry(case_id: str, principal: Member, session: DBSession) -> dict:
    _historical_comparables_enabled()
    if not get_settings().saas_company_reviewed_contract_registry_enabled:
        raise HTTPException(404,"Reviewed contract registry disabled")
    return company_historical_comparables.published_contract_catalog(session,principal,case_id)
