from typing import Literal

from pydantic import Field

from src.modules.procurement_portfolio.schemas import (
    ProcurementPortfolioSummaryResponse,
)
from src.shared.enums import DealStatus
from src.shared.types.common import APIModel


class CommercialOperatorActionRequest(APIModel):
    action: Literal["rejected", "needs_more_review", "collect_tkp", "prepare_bid_draft"]
    operator_ref: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class CommercialOperatorActionResponse(APIModel):
    deal_id: str
    action: str
    decision_id: str
    recorded_event_id: str


class KanbanStatusTransitionRequest(APIModel):
    to_status: DealStatus
    operator_ref: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class OperatorWorkflowBlocker(APIModel):
    code: str
    severity: str
    summary: str
    source_ref: str | None = None


class OperatorWorkflowItem(APIModel):
    deal_id: str
    procurement_number: str | None
    title: str
    current_status: str
    funnel_stage: str
    decision: str
    readiness_status: str | None
    blockers: list[OperatorWorkflowBlocker]
    submitted: bool
    outcome: str | None


class OperatorWorkflowStage(APIModel):
    stage: str
    count: int
    items: list[OperatorWorkflowItem]


class OperatorWorkflowResponse(APIModel):
    kpis: ProcurementPortfolioSummaryResponse
    stage_counts: dict[str, int]
    readiness_counts: dict[str, int]
    blocker_count: int
    stages: list[OperatorWorkflowStage]
