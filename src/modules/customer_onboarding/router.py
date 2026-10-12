"""APR-04 onboarding: compose existing versioned company/customer primitives.

Operator-scoped v1: authentication is the existing pilot Basic gate. This is NOT
a multi-tenant self-service or permission model (APR-05).
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import Field, model_validator
from sqlalchemy import or_, select

from src.modules.company_profile_store.schemas import (
    AppendCompanyProfileFactRequest,
    CreateCompanyDocumentRequest,
)
from src.modules.company_profile_store.service import (
    append_company_profile_fact,
    create_company_document,
    fact_state,
    get_company_document,
    list_company_documents,
    list_current_company_profile_facts,
)
from src.modules.customer_registry.models import CustomerProfile
from src.modules.customer_registry.schemas import CreateCustomerRequest
from src.modules.customer_registry.service import create_customer, get_customer
from src.modules.document_store.schemas import CreateArtifactRequest
from src.modules.document_store.service import create_artifact
from src.modules.tender_operator_agent_demo.fast_preanalysis import (
    fast_cited_preanalysis,
    preanalysis_from_public_search,
)
from src.modules.tender_operator_agent_demo.supplier_profile import (
    SupplierProfileCommercialConstraints,
    SupplierProfileCriteria,
    SupplierProfileQualification,
    SupplierProfileRiskPreferences,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_uploaded_demo_report,
)
from src.shared.api.dependencies import DBSession
from src.shared.config.settings import get_settings
from src.shared.types.common import APIModel

router = APIRouter(tags=["customer-onboarding"])
FACT_KEY = "supplier_profile"
MAX_PDF = 8 * 1024 * 1024
DOC_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
DOC_TYPES = {"STATUTORY", "LICENSE", "CERTIFICATE", "EXPERIENCE", "REQUISITES", "TEMPLATE"}


class OnboardingProfile(APIModel):
    criteria: SupplierProfileCriteria
    commercial: SupplierProfileCommercialConstraints = Field(
        default_factory=SupplierProfileCommercialConstraints
    )
    qualification: SupplierProfileQualification = Field(
        default_factory=SupplierProfileQualification
    )
    risk_preferences: SupplierProfileRiskPreferences = Field(
        default_factory=SupplierProfileRiskPreferences
    )

    @model_validator(mode="after")
    def valid_boundaries(self):
        criteria = self.criteria
        if not criteria.categories and not criteria.keywords:
            raise ValueError("Specify at least one procurement category or keyword")
        low, high = criteria.price_min, criteria.price_max
        if low is not None and (low < 0 or not float(low) < float("inf")):
            raise ValueError("NMCK minimum must be finite and nonnegative")
        if high is not None and (high < 0 or not float(high) < float("inf")):
            raise ValueError("NMCK maximum must be finite and nonnegative")
        if low is not None and high is not None and low > high:
            raise ValueError("NMCK minimum cannot exceed maximum")
        margin = self.commercial.target_margin_percent
        if margin is not None and not 0 <= margin <= 100:
            raise ValueError("Target margin must be between 0 and 100 percent")
        if self.qualification.experience_years is not None and self.qualification.experience_years < 0:
            raise ValueError("Experience cannot be negative")
        return self


class CreateOnboardingRequest(OnboardingProfile):
    legal_name: str = Field(min_length=2, max_length=512)
    inn: str | None = Field(default=None, pattern=r"^(?:\d{10}|\d{12})$")
    kpp: str | None = Field(default=None, pattern=r"^\d{9}$")


class TenderScreenRequest(APIModel):
    reference: str = Field(min_length=19, max_length=512)


def _profile(session: DBSession, customer_id: str) -> tuple[dict | None, int | None, str]:
    rows = list_current_company_profile_facts(session, customer_id=customer_id)
    version = next((item for item in rows if item.fact_key == FACT_KEY), None)
    if version is None:
        return None, None, "MISSING"
    _, _, state = fact_state(version, latest_version_no=version.version_no)
    value = version.value_json if state == "ACTIVE" and isinstance(version.value_json, dict) else None
    return value, version.version_no, state


def _save_profile(session: DBSession, customer_id: str, payload: OnboardingProfile):
    return append_company_profile_fact(
        session,
        customer_id=customer_id,
        fact_key=FACT_KEY,
        payload=AppendCompanyProfileFactRequest(
            fact_group="OTHER",
            value=payload.model_dump(mode="json"),
            source_type="CUSTOMER_PROVIDED",
            source_ref="APR04_ONBOARDING_OPERATOR_INPUT",
        ),
    )


@router.post("/api/onboarding/customers", status_code=status.HTTP_201_CREATED)
def onboard_company(payload: CreateOnboardingRequest, session: DBSession) -> dict:
    # Customer registry traditionally returns existing customers as duplicate.
    # Onboarding must fail closed, never overwrite another customer's profile.
    normalized = payload.legal_name.strip()
    if not normalized:
        raise HTTPException(422, "Legal name is required")
    clause = CustomerProfile.legal_name == normalized
    if payload.inn:
        clause = or_(clause, CustomerProfile.inn == payload.inn)
    if session.scalar(select(CustomerProfile).where(clause)):
        raise HTTPException(409, "Company already exists; use its explicit customer ID")
    record, duplicate_hint = create_customer(
        session,
        CreateCustomerRequest(legal_name=normalized, inn=payload.inn, kpp=payload.kpp),
    )
    if duplicate_hint:
        raise HTTPException(409, "Duplicate company requires operator review")
    saved = _save_profile(session, record.customer_id, OnboardingProfile.model_validate(payload.model_dump()))
    return {"customer_id": record.customer_id, "profile_version": saved.version_no, "status": "PROFILE_CAPTURED",
            "human_control_required": True, "documents_verified": False}


@router.put("/api/onboarding/customers/{customer_id}/profile")
def revise_profile(customer_id: str, payload: OnboardingProfile, session: DBSession) -> dict:
    saved = _save_profile(session, customer_id, payload)
    return {"customer_id": customer_id, "profile_version": saved.version_no, "status": "PROFILE_CAPTURED",
            "human_control_required": True}


@router.get("/api/onboarding/customers/{customer_id}")
def inspect_onboarding(customer_id: str, session: DBSession) -> dict:
    customer, _refs, _contours = get_customer(session, customer_id)
    profile, version, state = _profile(session, customer_id)
    documents = []
    for doc, versions in list_company_documents(session, customer_id=customer_id):
        latest = versions[-1]
        is_expired = bool(
            latest.expires_at and
            (latest.expires_at.replace(tzinfo=UTC) if latest.expires_at.tzinfo is None else latest.expires_at)
            <= datetime.now(UTC)
        )
        documents.append({
            "document_key": doc.document_key,
            "type": doc.document_type,
            "name": doc.display_name,
            "artifact_ref": doc.artifact_ref,
            "version": latest.version_no,
            "expires_at": latest.expires_at.isoformat() if latest.expires_at else None,
            "source_type": latest.source_type,
            "source_ref": latest.source_ref,
            "verified_by_operator": False,
            "requires_expiry_review": is_expired,
        })
    return {
        "customer_id": customer.customer_id,
        "legal_name": customer.legal_name, "inn": customer.inn, "kpp": customer.kpp,
        "profile": profile, "profile_version": version, "profile_state": state,
        "documents": documents,
        "status": "READY_FOR_HUMAN_SCREENING" if profile else "PROFILE_REQUIRED",
        "human_control_required": True,
    }


@router.post("/api/onboarding/customers/{customer_id}/documents", status_code=201)
async def upload_company_document(
    customer_id: str,
    session: DBSession,
    file: Annotated[UploadFile, File()],
    document_key: str = Form(...),
    document_type: str = Form(...),
    display_name: str = Form(...),
    expires_at: str | None = Form(None),
) -> dict:
    # Verify target exists before touching the filesystem.
    get_customer(session, customer_id)
    if not DOC_KEY.fullmatch(document_key) or document_type not in DOC_TYPES:
        raise HTTPException(422, "Invalid document key or document type")
    if not display_name.strip() or len(display_name) > 256:
        raise HTTPException(422, "Invalid document display name")
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(415, "Only PDF files are accepted")
    contents = await file.read(MAX_PDF + 1)
    if len(contents) > MAX_PDF:
        raise HTTPException(413, "File too large")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(415, "Invalid PDF content")
    parsed_expiry = None
    if expires_at:
        try:
            parsed_expiry = datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise HTTPException(422, "Invalid expiry date") from exc
    # The document key is unique per company, so reject before registering files.
    from src.modules.company_profile_store.models import CompanyDocument
    if session.scalar(select(CompanyDocument).where(
        CompanyDocument.customer_id == customer_id,
        CompanyDocument.document_key == document_key,
    )):
        raise HTTPException(409, "A document with this key is already registered")
    root = Path(get_settings().arvectum_data_dir).resolve() / "company-onboarding" / customer_id
    root.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.pdf"
    path = root / filename
    checksum = hashlib.sha256(contents).hexdigest()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(contents)
        artifact = create_artifact(
            session, CreateArtifactRequest(
                artifact_type="OTHER", file_name=filename, mime_type="application/pdf",
                storage_uri=str(path), checksum_sha256=checksum,
            ),
        )
        doc, _ = create_company_document(
            session,
            customer_id=customer_id,
            payload=CreateCompanyDocumentRequest(
                document_key=document_key, document_type=document_type,
                display_name=display_name.strip(), artifact_ref=artifact.artifact_ref,
                artifact_version_no=1, expires_at=parsed_expiry,
                source_type="CUSTOMER_UPLOADED", source_ref=f"sha256:{checksum}",
            ),
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"customer_id": customer_id, "document_key": doc.document_key,
            "artifact_ref": doc.artifact_ref, "sha256": checksum,
            "status": "UPLOADED_UNVERIFIED", "human_control_required": True}


@router.get("/api/onboarding/customers/{customer_id}/documents/{document_key}/download")
def download_company_document(customer_id: str, document_key: str, session: DBSession):
    doc, versions = get_company_document(session, customer_id=customer_id, document_key=document_key)
    from src.modules.company_profile_store.service import artifact_version_evidence

    evidence = artifact_version_evidence(
        session, artifact_ref=doc.artifact_ref, artifact_version_no=versions[-1].artifact_version_no,
    )
    path = Path(evidence.storage_uri)
    root = Path(get_settings().arvectum_data_dir).resolve() / "company-onboarding" / customer_id
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Onboarding file not found")
    if evidence.checksum_sha256 and hashlib.sha256(path.read_bytes()).hexdigest() != evidence.checksum_sha256:
        raise HTTPException(409, "Document checksum mismatch")
    return FileResponse(path, media_type="application/pdf", filename=f"{doc.document_key}.pdf")


def _price(value) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return None
    normalized = value.replace("\u00a0", "").replace(" ", "").replace(",", ".").replace("₽", "")
    normalized = re.sub(r"(руб(?:лей|ля|ль|\.|)|RUB)$", "", normalized, flags=re.IGNORECASE)
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def compare_profile_price(profile: OnboardingProfile, screening: dict) -> dict:
    price_fact = screening.get("initial_price") or {}
    if price_fact.get("status") != "KNOWN" or not price_fact.get("citations"):
        return {"status": "UNKNOWN", "reason": "Tender price lacks source citations", "citations": []}
    price = _price(price_fact.get("value"))
    if price is None:
        return {"status": "UNKNOWN", "reason": "Tender price cannot be parsed", "citations": []}
    low, high = profile.criteria.price_min, profile.criteria.price_max
    within = (low is None or price >= Decimal(str(low))) and (high is None or price <= Decimal(str(high)))
    return {"status": "WITHIN_BOUNDS" if within else "OUTSIDE_BOUNDS",
            "price_rub": str(price), "citations": price_fact["citations"],
            "reason": "Numeric NMCK boundary comparison, not a participation decision"}


def personalized_projection(
    customer_id: str, profile_version: int, profile: OnboardingProfile, screening: dict,
) -> dict:
    assessment = compare_profile_price(profile, screening)
    return {
        "contract_version": "apr04-personalized-screen-v1", "customer_id": customer_id,
        "profile_version": profile_version,
        "source": "customer_profile_plus_cited_preanalysis",
        "tender": screening,
        "profile_checks": {
            "nmck": assessment,
            "category": {"status": "UNKNOWN", "reason": "Category match requires reviewed document evidence"},
            "qualification": {"status": "UNKNOWN", "reason": "Uploaded licenses/SRO are not independently verified"},
            "margin_and_risks": {"status": "UNKNOWN", "reason": "Contract economics require human review"},
        },
        "decision": "HUMAN_REVIEW_REQUIRED", "external_action_allowed": False,
        "human_control_required": True,
    }


@router.post("/api/onboarding/customers/{customer_id}/screen")
def personalized_screening(customer_id: str, payload: TenderScreenRequest, session: DBSession) -> dict:
    profile_json, version, state = _profile(session, customer_id)
    if profile_json is None or version is None:
        raise HTTPException(409, f"Active company profile required: {state}")
    profile = OnboardingProfile.model_validate(profile_json)
    try:
        screening = preanalysis_from_public_search(payload.reference)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return personalized_projection(customer_id, version, profile, screening)


@router.post("/api/onboarding/customers/{customer_id}/runs/{run_id}/screen")
def personalized_uploaded_run_screening(customer_id: str, run_id: str, session: DBSession) -> dict:
    """Reuse an existing analyzed local run, no new tender/LLM execution."""
    profile_json, version, state = _profile(session, customer_id)
    if profile_json is None or version is None:
        raise HTTPException(409, f"Active company profile required: {state}")
    report = get_uploaded_demo_report(run_id)
    screening = fast_cited_preanalysis(report.decision_core)
    return personalized_projection(
        customer_id, version, OnboardingProfile.model_validate(profile_json), screening,
    )


@router.get("/pilot/onboarding", response_class=HTMLResponse)
def onboarding_page() -> str:
    from src.modules.customer_onboarding.ui import render_onboarding_html

    return render_onboarding_html()
