from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.modules.procurement_portfolio.schemas import (
    ProcurementPortfolioSummaryResponse,
)
from src.shared.types.common import APIModel

MobileDecisionAction = Literal["GO", "NO_GO", "DEFER"]
MobileHumanDecision = Literal["PENDING", "GO", "NO_GO", "DEFER"]
MobileRecommendation = Literal["GO", "NO_GO", "NEEDS_REVIEW", "UNDECIDED"]
MobileAPNsEnvironment = Literal["sandbox", "production"]


class MobileDecisionRequest(APIModel):
    action: MobileDecisionAction
    rationale: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    deferred_until: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_defer(self):
        if self.action == "DEFER" and self.deferred_until is None:
            raise ValueError("deferred_until is required for DEFER")
        if self.action != "DEFER" and self.deferred_until is not None:
            raise ValueError("deferred_until is only allowed for DEFER")
        return self




class MobilePairRequest(APIModel):
    pairing_code: str = Field(min_length=6, max_length=6)
    device_id: str = Field(min_length=8, max_length=128)
    device_name: str | None = Field(default=None, max_length=128)


class MobilePairResponse(APIModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    device_id: str


class MobileDeviceRegistrationRequest(APIModel):
    apns_token: str = Field(min_length=32, max_length=256)
    environment: MobileAPNsEnvironment
    device_name: str | None = Field(default=None, max_length=128)
    app_version: str | None = Field(default=None, max_length=64)


class MobileDeviceRegistrationResponse(APIModel):
    device_id: str
    environment: MobileAPNsEnvironment
    device_name: str | None = None
    app_version: str | None = None
    enabled: bool
    registered_at: datetime
    updated_at: datetime


class MobileProcurementItemResponse(APIModel):
    deal_id: str
    procurement_number: str | None
    title: str
    customer_name: str | None
    source_url: str | None = None
    nmck_rub: float | None = None
    deadline_at: datetime | None = None

    recommendation: MobileRecommendation
    recommendation_rationale: str | None = None
    recommendation_reason_codes: list[str] = Field(default_factory=list)
    recommendation_confidence: str | None = None
    recommendation_reasons: list[str] = Field(default_factory=list)
    recommendation_blockers: list[str] = Field(default_factory=list)
    recommendation_unknowns: list[str] = Field(default_factory=list)
    analysis_run_id: str | None = None
    analysis_report_path: str | None = None

    human_decision: MobileHumanDecision
    human_rationale: str | None = None
    human_reason_codes: list[str] = Field(default_factory=list)
    deferred_until: datetime | None = None
    needs_attention: bool

    submitted: bool
    submitted_at: datetime | None
    outcome: str | None
    outcome_rationale: str | None
    outcome_at: datetime | None
    postmortem_root_cause: str | None
    current_status: str
    updated_at: datetime


class MobileInboxSummaryResponse(APIModel):
    total_portfolio: int
    needs_attention: int
    deferred: int
    submitted: int
    won: int
    lost: int
    cancelled: int


class MobileInboxResponse(APIModel):
    summary: MobileInboxSummaryResponse
    items: list[MobileProcurementItemResponse]


class MobilePortfolioResponse(APIModel):
    summary: ProcurementPortfolioSummaryResponse
    items: list[MobileProcurementItemResponse]


class MobileDigestResponse(APIModel):
    run_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    counts: dict = Field(default_factory=dict)
    actionable: list[dict] = Field(default_factory=list)
    human_control: dict = Field(default_factory=dict)
