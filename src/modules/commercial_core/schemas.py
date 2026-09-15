from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from src.shared.types.common import APIModel


class CatalogImportStatus(StrEnum):
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CatalogMatchStatus(StrEnum):
    EXACT = "EXACT"
    LIKELY_ANALOG = "LIKELY_ANALOG"
    PARTIAL = "PARTIAL"
    UNCERTAIN = "UNCERTAIN"
    NO_MATCH = "NO_MATCH"


class CommercialFeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_FEASIBLE_AT_CURRENT_CATALOG_PRICE = "NOT_FEASIBLE_AT_CURRENT_CATALOG_PRICE"


class CommercialCatalogRow(APIModel):
    row_id: str
    source_file: str
    sheet_name: str
    row_number: int
    sku: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    title: str
    unit: str | None = None
    price: float | None = None
    currency: str | None = None
    characteristics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CommercialCatalogImport(APIModel):
    status: CatalogImportStatus
    source_file: str
    source_sha256: str
    rows: list[CommercialCatalogRow] = Field(default_factory=list)
    detected_columns: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class CommercialPositionMatch(APIModel):
    position_id: str
    tender_name: str
    tender_quantity: float | None = None
    tender_unit: str | None = None
    status: CatalogMatchStatus
    catalog_row_id: str | None = None
    catalog_title: str | None = None
    catalog_unit: str | None = None
    catalog_unit_price: float | None = None
    currency: str | None = None
    match_score: float = 0.0
    rationale: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class CommercialCoverage(APIModel):
    total_positions: int
    exact: int
    likely_analog: int
    partial: int
    uncertain: int
    no_match: int
    matched_coverage_ratio: float | None = None
    costed_coverage_ratio: float | None = None


class CommercialEconomics(APIModel):
    status: str
    currency: str | None = None
    known_catalog_cost: float | None = None
    costed_position_ids: list[str] = Field(default_factory=list)
    unknown_cost_position_ids: list[str] = Field(default_factory=list)
    target_bid_amount: float | None = None
    gross_margin_amount: float | None = None
    gross_margin_percent: float | None = None
    nmck_ceiling: float | None = None
    nmck_headroom_amount: float | None = None
    nmck_headroom_percent: float | None = None
    warnings: list[str] = Field(default_factory=list)


class CommercialCoreResponse(APIModel):
    contract_version: str
    catalog: CommercialCatalogImport
    matches: list[CommercialPositionMatch] = Field(default_factory=list)
    coverage: CommercialCoverage
    economics: CommercialEconomics
    feasibility_status: CommercialFeasibilityStatus
    rationale: list[str] = Field(default_factory=list)
    next_action: str
    human_control_required: bool = True
    external_action_allowed: bool = False
    safety: dict[str, bool] = Field(default_factory=dict)
