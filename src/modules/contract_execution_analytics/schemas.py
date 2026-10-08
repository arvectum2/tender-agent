from datetime import datetime
from typing import Literal

from pydantic import Field

from src.shared.types.common import APIModel

FactState = Literal["OBSERVED", "UNKNOWN"]


class ExecutionEvidenceResponse(APIModel):
    source_type: str
    source_ref: str
    field: str | None = None
    value: str | None = None
    source_url: str | None = None
    observed_at: datetime | None = None


class LifecycleFactResponse(APIModel):
    state: FactState
    value_text: str | None = None
    value_numeric: float | None = None
    currency_code: str | None = None
    observed_at: datetime | None = None
    summary: str
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class ExecutionStageResponse(APIModel):
    stage_code: str
    stage_name: str
    state: FactState
    status: str | None = None
    due_at: datetime | None = None
    observed_at: datetime | None = None
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class PaymentAnalyticsResponse(APIModel):
    state: FactState
    status: str | None = None
    expected_amount: float | None = None
    collected_amount: float | None = None
    currency_code: str | None = None
    overdue_days: int | None = None
    summary: str
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class TimingAnalyticsResponse(APIModel):
    state: FactState
    current_phase: str | None = None
    milestone_count: int = 0
    delayed_milestone_count: int | None = None
    overdue_payment_days: int | None = None
    summary: str
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class RiskSignalResponse(APIModel):
    signal_code: str
    severity: str | None = None
    summary: str
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class PenaltyClaimAnalyticsResponse(APIModel):
    state: FactState
    claim_status: str | None = None
    monetary_penalty_state: FactState = "UNKNOWN"
    monetary_penalty_amount: float | None = None
    summary: str
    signals: list[RiskSignalResponse] = Field(default_factory=list)
    evidence: list[ExecutionEvidenceResponse] = Field(default_factory=list)


class ContractExecutionAnalyticsResponse(APIModel):
    deal_id: str
    procurement_number: str | None = None
    procurement: LifecycleFactResponse
    supplier_contract: LifecycleFactResponse
    execution: LifecycleFactResponse
    execution_stages: list[ExecutionStageResponse] = Field(default_factory=list)
    payment: PaymentAnalyticsResponse
    timing: TimingAnalyticsResponse
    penalties: PenaltyClaimAnalyticsResponse
    actual_price: LifecycleFactResponse
    outcome: LifecycleFactResponse
    closure: LifecycleFactResponse
    postmortem: LifecycleFactResponse
    closure_health: LifecycleFactResponse
    learning_promotion_performed: bool = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Missing canonical records remain UNKNOWN and are never treated as proof that an event did not occur.",
            "Collected payment is cash-receipt evidence and is not relabeled as final/actual contract price.",
            "Claim or incident signals are not converted into a monetary penalty unless a typed canonical amount exists.",
            "This endpoint is read-only and does not promote postmortem/KPI facts into autonomous learning or scoring.",
        ]
    )
