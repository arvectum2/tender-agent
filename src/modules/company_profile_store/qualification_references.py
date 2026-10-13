"""Tenant-scoped, source-bound competitive qualification against completed contract references.

The reference list is an immutable-version CompanyProfileFactVersion with fact
key 'completed_contract_reference_list' and fact_group EXPERIENCE. Absence of a
fact means UNKNOWN, never an empty list. This module never authorizes bids.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, model_validator
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.models import CompanyProfileFactVersion
from src.modules.customer_registry.models import CustomerProfile
from src.shared.errors import NotFoundError
from src.shared.types.common import APIModel

REFERENCE_FACT_KEY = "completed_contract_reference_list"
REFERENCE_SCHEMA = "completed-contract-references-v1"
ASSESSMENT_SCHEMA = "qualification-reference-assessment-v1"
EIS_FZ_NUMBER = re.compile(r"[0-9]{19}\Z")
EIS_UID = re.compile(r"[A-F0-9]{32}\Z")
HEX_SHA256 = re.compile(r"[a-f0-9]{64}\Z")

Law = Literal["44fz", "223fz"]
Subject = Literal["website", "web_portal", "information_system", "module"]


class CompletedContractReference(APIModel):
    law: Law
    contract_number: str = Field(min_length=1)
    subject: Subject
    chatbot_in_scope: bool
    completed: bool
    acceptance_signed_at: date | None = None
    contract_document_ref: str | None = None
    signed_final_act_ref: str | None = None

    @model_validator(mode="after")
    def completed_requires_original_evidence(self):
        if self.completed and (
            self.acceptance_signed_at is None
            or not self.contract_document_ref
            or not self.signed_final_act_ref
        ):
            raise ValueError("Completed contract requires signed final act date and both source references")
        return self


class CompletedContractReferenceSnapshot(APIModel):
    schema_version: Literal["completed-contract-references-v1"]
    as_of_date: date
    completeness: Literal["COMPLETE", "PARTIAL"]
    owner_confirmed: bool
    contracts: list[CompletedContractReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def empty_list_requires_owner(self):
        if self.completeness == "COMPLETE" and not self.owner_confirmed:
            raise ValueError("A complete list requires owner confirmation")
        identifiers = [(x.law, x.contract_number.strip()) for x in self.contracts]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate contract reference")
        return self


class QualificationCriterion(APIModel):
    procurement_number: str
    procurement_law: Law
    procurement_notice_version: int = Field(ge=1)
    source_document_uid: str
    source_document_sha256: str
    qualification_weight_percent: int = Field(ge=0, le=100)
    price_weight_percent: int = Field(ge=0, le=100)
    metric: Literal["completed_contract_count"] = "completed_contract_count"
    accepted_contract_laws: list[Law] = Field(min_length=1)
    accepted_subjects: list[Subject] = Field(min_length=1)
    requires_chatbot: bool
    lookback_years: int = Field(ge=1, le=20)
    analysis_date: date

    @model_validator(mode="after")
    def strict_official_source(self):
        if not EIS_FZ_NUMBER.fullmatch(self.procurement_number):
            raise ValueError("Only exact EIS registry number is supported")
        if not EIS_UID.fullmatch(self.source_document_uid):
            raise ValueError("Official attached document UID is required")
        if not HEX_SHA256.fullmatch(self.source_document_sha256):
            raise ValueError("Original attached document checksum is required")
        if self.price_weight_percent + self.qualification_weight_percent != 100:
            raise ValueError("Scoring weights must sum to 100 for this criterion")
        if len(self.accepted_contract_laws) != len(set(self.accepted_contract_laws)):
            raise ValueError("Duplicate accepted contract laws")
        if len(self.accepted_subjects) != len(set(self.accepted_subjects)):
            raise ValueError("Duplicate accepted subjects")
        return self


class QualificationAssessment(APIModel):
    contract_version: Literal["qualification-reference-assessment-v1"] = ASSESSMENT_SCHEMA
    customer_id: str
    procurement_number: str
    procurement_notice_version: int
    source_document_uid: str
    source_document_sha256: str
    criterion: dict
    reference_fact_version: int | None = None
    reference_fact_source_type: str | None = None
    reference_fact_source_ref: str | None = None
    reference_snapshot_as_of: date | None = None
    reference_list_state: Literal["UNKNOWN", "EXPIRED", "PARTIAL", "CONFIRMED_COMPLETE"]
    qualifying_contracts: int | None = None
    recommendation: Literal[
        "QUALIFICATION_EVIDENCE_UNKNOWN",
        "QUALIFICATION_EVIDENCE_EXPIRED",
        "QUALIFICATION_EVIDENCE_PARTIAL",
        "NO_GO_QUALIFICATION_COMPETITIVENESS",
        "COMPETITIVE_RISK_NOT_AUTOMATIC_NO_GO",
        "QUALIFYING_REFERENCES_PRESENT_REVIEW_SCORE",
    ]
    reasons: list[str] = Field(default_factory=list)
    eligibility_status: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    technical_feasibility_status: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    predicted_win_probability: None = None
    customer_owner_approval: bool = False
    human_gold: bool = False
    external_action_allowed: bool = False


def _cutoff(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February
        return d.replace(year=d.year - years, day=28)


def assess_references(
    *,
    customer_id: str,
    criterion: QualificationCriterion,
    snapshot: CompletedContractReferenceSnapshot | None,
    fact_version: int | None = None,
    fact_source_type: str | None = None,
    fact_source_ref: str | None = None,
    expired: bool = False,
) -> QualificationAssessment:
    """Deterministic conservative assessment, no user reference inferred from absence."""
    common = {
        "customer_id": customer_id,
        "procurement_number": criterion.procurement_number,
        "procurement_notice_version": criterion.procurement_notice_version,
        "source_document_uid": criterion.source_document_uid,
        "source_document_sha256": criterion.source_document_sha256,
        "criterion": criterion.model_dump(mode="json"),
        "reference_fact_version": fact_version,
        "reference_fact_source_type": fact_source_type,
        "reference_fact_source_ref": fact_source_ref,
        "reference_snapshot_as_of": snapshot.as_of_date if snapshot else None,
    }
    if expired:
        return QualificationAssessment(**common, reference_list_state="EXPIRED",
            recommendation="QUALIFICATION_EVIDENCE_EXPIRED",
            reasons=["Latest reference-list version has expired; cannot treat as zero."])
    if snapshot is None:
        return QualificationAssessment(**common, reference_list_state="UNKNOWN",
            recommendation="QUALIFICATION_EVIDENCE_UNKNOWN",
            reasons=["No valid owner-confirmed completed-contract list exists for this customer."])
    if snapshot.as_of_date > criterion.analysis_date or not snapshot.owner_confirmed:
        return QualificationAssessment(**common, reference_list_state="UNKNOWN",
            recommendation="QUALIFICATION_EVIDENCE_UNKNOWN",
            reasons=["Reference-list date/owner confirmation is not valid for this analysis."])
    if snapshot.completeness != "COMPLETE":
        return QualificationAssessment(**common, reference_list_state="PARTIAL",
            recommendation="QUALIFICATION_EVIDENCE_PARTIAL",
            reasons=["Incomplete contract list cannot prove absence of qualifying contracts."])
    cutoff = _cutoff(criterion.analysis_date, criterion.lookback_years)
    qualifying = [
        contract for contract in snapshot.contracts
        if (
            contract.completed
            and contract.law in criterion.accepted_contract_laws
            and contract.subject in criterion.accepted_subjects
            and (not criterion.requires_chatbot or contract.chatbot_in_scope)
            and contract.acceptance_signed_at is not None
            and cutoff <= contract.acceptance_signed_at <= criterion.analysis_date
            and bool(contract.contract_document_ref)
            and bool(contract.signed_final_act_ref)
        )
    ]
    count = len(qualifying)
    if count:
        verdict = "QUALIFYING_REFERENCES_PRESENT_REVIEW_SCORE"
        reason = "Completed matching signed contract references found; final scoring also depends on competitors and official formula."
    elif criterion.qualification_weight_percent >= 60:
        verdict = "NO_GO_QUALIFICATION_COMPETITIVENESS"
        reason = (
            "Zero qualifying completed contracts in owner-confirmed complete reference list; "
            "qualification controls at least 60% of scoring. Commercial NO_GO, not legal ineligibility."
        )
    else:
        verdict = "COMPETITIVE_RISK_NOT_AUTOMATIC_NO_GO"
        reason = "No qualifying completed contracts; qualification weight does not independently justify an automatic competitive NO_GO."
    return QualificationAssessment(
        **common, reference_list_state="CONFIRMED_COMPLETE",
        qualifying_contracts=count, recommendation=verdict, reasons=[reason],
    )


def assess_company_qualification(
    session: Session, *, customer_id: str, criterion: QualificationCriterion
) -> QualificationAssessment:
    """Read only the latest immutable fact for this tenant, no demo/global fallback."""
    if session.scalar(select(CustomerProfile.id).where(
        CustomerProfile.customer_id == customer_id
    )) is None:
        raise NotFoundError(f"Customer '{customer_id}' was not found")
    record = session.scalar(
        select(CompanyProfileFactVersion)
        .where(
            CompanyProfileFactVersion.customer_id == customer_id,
            CompanyProfileFactVersion.fact_key == REFERENCE_FACT_KEY,
        )
        .order_by(CompanyProfileFactVersion.version_no.desc())
        .limit(1)
    )
    if record is None:
        return assess_references(customer_id=customer_id, criterion=criterion, snapshot=None)
    now = datetime.now(UTC)
    expired = False
    if record.expires_at is not None:
        expiry = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=UTC)
        expired = expiry <= now
    snapshot = None
    if record.fact_group == "EXPERIENCE" and record.source_type in {
        "CUSTOMER_PROVIDED", "OWNER_CONFIRMED"
    }:
        try:
            snapshot = CompletedContractReferenceSnapshot.model_validate(record.value_json)
        except PydanticValidationError:
            pass
    return assess_references(
        customer_id=customer_id, criterion=criterion, snapshot=snapshot,
        fact_version=record.version_no,
        fact_source_type=record.source_type,
        fact_source_ref=record.source_ref,
        expired=expired,
    )
