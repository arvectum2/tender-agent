from datetime import datetime
from typing import Literal

from pydantic import Field

from src.shared.enums import DirectionType
from src.shared.types.common import APIModel

PortfolioDecision = Literal["GO", "NO_GO", "NEEDS_REVIEW", "UNDECIDED"]
WritablePortfolioDecision = Literal["GO", "NO_GO", "NEEDS_REVIEW"]


class CreatePortfolioProcurementRequest(APIModel):
    procurement_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    source_url: str | None = None
    direction_type: DirectionType = DirectionType.OTHER
    domain_type: str = Field(default="GENERAL", min_length=1)


class RecordPortfolioDecisionRequest(APIModel):
    decision: WritablePortfolioDecision
    rationale: str = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    decided_by_ref: str | None = None


class ProcurementPortfolioItemResponse(APIModel):
    deal_id: str
    procurement_number: str | None
    title: str
    customer_name: str | None
    procurement_channel: str | None
    current_status: str
    priority_bucket: str | None
    decision: PortfolioDecision
    decision_source: str | None
    decision_rationale: str | None
    decision_reason_codes: list[str]
    decision_at: datetime | None
    screening_status: str | None
    screening_score: float | None
    screening_rationale: str | None
    screening_reason_codes: list[str]
    submitted: bool
    submitted_at: datetime | None
    outcome: str | None
    outcome_rationale: str | None
    outcome_at: datetime | None
    postmortem_root_cause: str | None
    created_at: datetime
    updated_at: datetime


class ProcurementPortfolioSummaryResponse(APIModel):
    total_considered: int
    go: int
    no_go: int
    needs_review: int
    undecided: int
    submitted: int
    won: int
    lost: int
    rejected: int
    cancelled: int
    submission_rate: float
    win_rate: float
    no_go_reason_counts: dict[str, int]


class ProcurementPortfolioResponse(APIModel):
    summary: ProcurementPortfolioSummaryResponse
    items: list[ProcurementPortfolioItemResponse]
