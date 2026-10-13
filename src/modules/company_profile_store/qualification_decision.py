"""Read-only integration of tenant references with the existing Tender Agent Decision Core.

The procurement evidence is independently supplied by a verified source adapter.
This integration never mutates legal/admissibility Decision Core status and is
not a substitute for independently verifying the official document digest.
"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from src.modules.company_profile_store.qualification_references import (
    QualificationAssessment,
    QualificationCriterion,
    assess_company_qualification,
)
from src.modules.tender_operator_agent_demo.decision_core import build_decision_core
from src.shared.errors import ValidationError
from src.shared.types.common import APIModel
from sqlalchemy.orm import Session


class QualificationAwareDecisionRequest(APIModel):
    criterion: QualificationCriterion
    procurement_model: dict[str, Any] = Field(default_factory=dict)
    source_binding: dict[str, Any] = Field(default_factory=dict)


class QualificationAwareDecisionResponse(APIModel):
    assessment: QualificationAssessment
    decision_core: dict[str, Any]
    competitive_recommendation: str
    legal_eligibility_unchanged: bool = True
    external_action_allowed: bool = False


def build_qualification_aware_decision(
    session: Session,
    *,
    customer_id: str,
    request: QualificationAwareDecisionRequest,
) -> QualificationAwareDecisionResponse:
    """Consult fact store every run. Never use a global/demo supplier profile."""
    criterion = request.criterion
    model = request.procurement_model
    declared = request.source_binding
    expected = {
        "procurement_number": criterion.procurement_number,
        "notice_version": criterion.procurement_notice_version,
        "document_uid": criterion.source_document_uid,
        "document_sha256": criterion.source_document_sha256,
    }
    if declared != expected:
        raise ValidationError("Source-bound criterion is missing or conflicts with the original document")
    if model.get("procurement_number") != criterion.procurement_number:
        raise ValidationError("Procurement and qualification criterion numbers do not match")
    law = str(model.get("procurement_law") or "").lower().replace("-", "")
    if law != criterion.procurement_law:
        raise ValidationError("Procurement regime and scoring criterion do not match")
    qualification = assess_company_qualification(
        session, customer_id=customer_id, criterion=criterion
    )
    core = build_decision_core(model)
    # Keep legal compliance separate. No qualification-weight shortcut may make
    # a legally eligible bidder ineligible or override an actual hard blocker.
    core["competitive_qualification"] = qualification.model_dump(mode="json")
    commercial = (
        "NO_GO"
        if qualification.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"
        else "HUMAN_REVIEW_REQUIRED"
    )
    core["decision"]["competitive_recommendation"] = commercial
    core["decision"]["qualification_reference_list_state"] = qualification.reference_list_state
    core["decision"]["human_control_required"] = True
    core["decision"]["external_action_allowed"] = False
    return QualificationAwareDecisionResponse(
        assessment=qualification,
        decision_core=core,
        competitive_recommendation=commercial,
    )
