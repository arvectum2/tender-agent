from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.shared.types.common import APIModel


class DailyTenderDecisionPolicy(APIModel):
    positive_signals: list[str] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)
    review_signals: list[str] = Field(default_factory=list)
    non_blockers: list[str] = Field(default_factory=list)


class DailyTenderProfile(APIModel):
    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    law: str = "44fz"
    queries: list[str] = Field(min_length=1)
    lookback_days: int = Field(default=2, ge=0, le=30)
    status_filter: str | None = "Подача заявок"
    max_results_per_query: int = Field(default=20, ge=1, le=50)
    max_deep_analysis: int = Field(default=20, ge=1, le=100)
    min_nmck: float | None = Field(default=None, ge=0)
    max_nmck: float | None = Field(default=None, ge=0)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    require_include_keyword: bool = True
    require_custom_work_keyword: bool = False
    custom_work_keywords: list[str] = Field(default_factory=list)
    strong_custom_work_keywords: list[str] = Field(default_factory=list)
    license_supply_keywords: list[str] = Field(default_factory=list)
    support_only_keywords: list[str] = Field(default_factory=list)
    security_infra_keywords: list[str] = Field(default_factory=list)
    preferred_max_nmck: float | None = Field(default=None, ge=0)
    decision_policy: DailyTenderDecisionPolicy = Field(
        default_factory=DailyTenderDecisionPolicy
    )
    analysis_mode: Literal["fast", "balanced", "detailed"] = "balanced"
    analysis_use_llm: bool = True
    synthesis_use_llm: bool = True


class StartDailyTenderRunRequest(APIModel):
    profile_id: str = "arvectum-it"
    run_now: bool = True
    retry_failed: bool = False


class DailyTenderRunItemResponse(APIModel):
    registry_number: str
    law: str
    source: str
    source_url: str | None
    title: str
    customer_name: str | None
    nmck_amount: float | None
    deadline_at: datetime | None
    query_hits: list[str] = Field(default_factory=list)
    stage: str
    status: str
    screening_status: str | None
    screening_score: float | None
    screening_reasons: list[str] = Field(default_factory=list)
    changed_since_previous: bool
    deal_id: str | None
    analysis_run_id: str | None
    analysis_status: str | None
    analysis_report_path: str | None
    agent_recommendation: str | None
    agent_confidence: str | None
    agent_rationale: str | None
    strongest_reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    human_decision: str | None = None
    human_decision_id: str | None = None
    post_decision: dict = Field(default_factory=dict)
    error: str | None
    created_at: datetime
    updated_at: datetime


class DailyTenderRunResponse(APIModel):
    run_id: str
    profile_id: str
    profile_version: str
    status: str
    current_stage: str
    counts: dict
    digest: dict | None
    error_summary: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[DailyTenderRunItemResponse] = Field(default_factory=list)
