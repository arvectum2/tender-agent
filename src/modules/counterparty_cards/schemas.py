from datetime import datetime
from typing import Literal

from pydantic import Field

from src.shared.types.common import APIModel


class CounterpartyEvidenceRefResponse(APIModel):
    source_type: str
    source_ref: str
    label: str
    url: str | None = None


class CounterpartyFactorResponse(APIModel):
    factor_code: str
    category: str
    state: Literal["OBSERVED", "ADVERSE", "UNKNOWN"]
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
    risk_points: float | None = None
    contributes_to_score: bool = False
    summary: str
    evidence: list[CounterpartyEvidenceRefResponse] = Field(default_factory=list)


class CounterpartyRiskAggregateResponse(APIModel):
    available: bool
    observed_risk_score: float | None = None
    source_confidence_score: float | None = None
    band: Literal[
        "INSUFFICIENT_EVIDENCE",
        "PASS",
        "NEEDS_REVIEW",
        "FAIL",
    ]
    calculation: str
    included_factor_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    authoritative_reliability_conclusion: bool = False
    participation_decision: bool = False


class CounterpartyHistoryItemResponse(APIModel):
    history_type: Literal["PROCUREMENT", "SUPPLIER_CONTRACT"]
    record_id: str
    title: str
    status: str | None = None
    amount: float | None = None
    currency: str | None = None
    occurred_at: datetime | None = None
    evidence: list[CounterpartyEvidenceRefResponse] = Field(default_factory=list)


class CounterpartyHistoryResponse(APIModel):
    procurement_count: int = 0
    procurement_nmck_total: float | None = None
    supplier_contract_count: int = 0
    items: list[CounterpartyHistoryItemResponse] = Field(default_factory=list)


class CounterpartyCardResponse(APIModel):
    counterparty_type: Literal["CUSTOMER", "SUPPLIER"]
    counterparty_id: str
    legal_name: str
    inn: str | None = None
    profile_status: str | None = None
    factors: list[CounterpartyFactorResponse] = Field(default_factory=list)
    risk: CounterpartyRiskAggregateResponse
    history: CounterpartyHistoryResponse
