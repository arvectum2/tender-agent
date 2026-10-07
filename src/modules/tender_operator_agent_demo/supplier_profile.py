from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from src.shared.types.common import APIModel


class RiskTolerance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VATMode(StrEnum):
    WITH_VAT = "with_vat"
    WITHOUT_VAT = "without_vat"
    BOTH = "both"


class SupplierProfileCriteria(APIModel):
    categories: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    keywords: list[str] = Field(default_factory=list)
    stop_words: list[str] = Field(default_factory=list)


class SupplierProfileCommercialConstraints(APIModel):
    vat_mode: VATMode | None = None
    target_margin_percent: float | None = None
    max_payment_delay_days: int | None = None
    max_contract_security_percent: float | None = None
    max_prepayment_gap: float | None = None
    max_cash_gap: float | None = None


class SupplierProfileQualification(APIModel):
    licenses: list[str] = Field(default_factory=list)
    sro_approvals: list[str] = Field(default_factory=list)
    experience_years: float | None = None


class SupplierProfileRiskPreferences(APIModel):
    tolerance: RiskTolerance | None = RiskTolerance.MEDIUM
    max_penalty_percent: float | None = None
    max_delay_days: int | None = None
    require_certificates: bool | None = True
    risky_categories: list[str] = Field(default_factory=list)
    forbidden_categories: list[str] = Field(default_factory=list)


class SupplierProfile(APIModel):
    supplier_id: str
    name: str
    short_name: str | None = None
    inn: str | None = None
    description: str | None = None
    criteria: SupplierProfileCriteria = Field(default_factory=SupplierProfileCriteria)
    commercial: SupplierProfileCommercialConstraints = Field(default_factory=SupplierProfileCommercialConstraints)
    qualification: SupplierProfileQualification = Field(default_factory=SupplierProfileQualification)
    risk_preferences: SupplierProfileRiskPreferences = Field(default_factory=SupplierProfileRiskPreferences)
    certificates: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load_demo_fixture(cls) -> SupplierProfile:
        import json
        import os

        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "demo_data", "tender_operator_agent",
            "supplier_profile_electrical.json",
        )
        resolved = os.path.normpath(fixture_path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(
                f"Demo supplier profile fixture not found at {resolved}. "
                "Ensure demo_data/tender_operator_agent/supplier_profile_electrical.json exists."
            )
        with open(resolved, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def _profile_value(text: str, label: str) -> str | None:
    pattern = (
        rf"^-\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?"
        rf"(?:\s*\([^\n:]*\))?\s*:\s*(.*?)\s*$"
    )
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _profile_section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    rest = text[match.end():]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def _profile_list(section: str) -> list[str]:
    values: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-") or re.match(r"^-\s*\[[ xX]\]", line):
            continue
        value = line[1:].strip()
        if not value or value.endswith(":") or re.match(r"^Category\s+\d+\s*:\s*$", value, re.IGNORECASE):
            continue
        if ":" in value:
            _, candidate = value.split(":", 1)
            value = candidate.strip()
        if value:
            values.append(value)
    return values


def _split_inline_list(value: str | None) -> list[str]:
    if not value:
        return []
    delimiter = ";" if ";" in value else ","
    return [item.strip() for item in value.split(delimiter) if item.strip()]


def _profile_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d[\d\s,._]*", value)
    if not match:
        return None
    raw = match.group(0).replace(" ", "").replace("_", "")
    if raw.count(",") == 1 and "." not in raw and len(raw.split(",", 1)[1]) <= 2:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _nonnegative(value: str | None) -> float | None:
    number = _profile_number(value)
    return number if number is not None and number >= 0 else None


def _percent(value: str | None) -> float | None:
    number = _nonnegative(value)
    return number if number is not None and number <= 100 else None


def _whole_days(value: str | None) -> int | None:
    number = _nonnegative(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _vat_mode(text: str) -> VATMode | None:
    checked: list[str] = []
    for line in _profile_section(text, "VAT Mode").splitlines():
        match = re.match(r"^\s*-\s*\[[xX]\]\s*(.+?)\s*$", line)
        if match:
            checked.append(match.group(1).strip().lower())
    if len(checked) != 1:
        return None
    selected = checked[0]
    if "both" in selected:
        return VATMode.BOTH
    if "without vat" in selected:
        return VATMode.WITHOUT_VAT
    if "with vat" in selected:
        return VATMode.WITH_VAT
    return None


def _qualification_lists(text: str) -> tuple[list[str], list[str]]:
    licenses = _split_inline_list(_profile_value(text, "Licenses held"))
    sro = _split_inline_list(_profile_value(text, "SRO approvals held"))
    if licenses or sro:
        return licenses, sro

    section = _profile_section(text, "Licensing / SRO") or _profile_section(text, "Licensing")
    for item in _profile_list(section):
        lowered = item.lower()
        if "sro" in lowered:
            sro.append(item)
        elif not lowered.startswith(("no ", "none", "not ")):
            licenses.append(item)
    return licenses, sro


def parse_operator_profile_markdown(text: str, *, supplier_id: str) -> SupplierProfile | None:
    """Parse the RFQ-first markdown contract into a validated supplier profile.

    Missing, contradictory or malformed business values stay empty/None. The
    parser does not infer catalog, price, qualification or risk facts that are
    not explicitly present in the profile.
    """

    if not text.strip():
        return None

    operator_name = _profile_value(text, "Operator Name")
    company_name = _profile_value(text, "Company Name")
    company_type = _profile_value(text, "Company Type")
    sectors = _profile_value(text, "Industry / Sectors") or _profile_value(text, "Industry")
    employee_count = _whole_days(_profile_value(text, "Company Size"))

    categories = _profile_list(_profile_section(text, "Working Categories"))
    excluded_categories = _profile_list(_profile_section(text, "Excluded Categories"))
    regions_raw = _profile_value(text, "Tender Regions") or _profile_value(text, "Regions")
    regions = _split_inline_list(regions_raw)

    price_min = _nonnegative(_profile_value(text, "Minimum"))
    price_max = _nonnegative(_profile_value(text, "Maximum"))
    if price_min is not None and price_max is not None and price_min > price_max:
        price_min = None
        price_max = None

    max_prepayment_gap = _nonnegative(_profile_value(text, "Maximum acceptable prepayment gap"))
    max_cash_gap = _nonnegative(
        _profile_value(text, "Maximum cash gap before customer payment")
        or _profile_value(text, "Maximum cash gap")
    )

    risky_categories = _split_inline_list(_profile_value(text, "Risky categories"))
    forbidden_categories = _split_inline_list(_profile_value(text, "Forbidden categories"))
    licenses, sro = _qualification_lists(text)

    metadata: dict[str, Any] = {"source_contract": "operator_profile.md"}
    if operator_name:
        metadata["operator_name"] = operator_name
    if company_type:
        metadata["company_type"] = company_type
    if sectors:
        metadata["sectors"] = sectors
    if employee_count is not None:
        metadata["employee_count"] = employee_count
    if not (company_name or operator_name):
        metadata["identity_fallback"] = True

    return SupplierProfile(
        supplier_id=supplier_id,
        name=company_name or operator_name or supplier_id,
        short_name=operator_name if company_name and operator_name else None,
        description=sectors,
        criteria=SupplierProfileCriteria(
            categories=categories,
            excluded_categories=excluded_categories,
            regions=regions,
            price_min=price_min,
            price_max=price_max,
        ),
        commercial=SupplierProfileCommercialConstraints(
            vat_mode=_vat_mode(text),
            target_margin_percent=_percent(_profile_value(text, "Target margin")),
            max_payment_delay_days=_whole_days(_profile_value(text, "Acceptable payment delay")),
            max_contract_security_percent=_percent(_profile_value(text, "Acceptable contract security")),
            max_prepayment_gap=max_prepayment_gap,
            max_cash_gap=max_cash_gap,
        ),
        qualification=SupplierProfileQualification(
            licenses=licenses,
            sro_approvals=sro,
            experience_years=_nonnegative(_profile_value(text, "Experience required")),
        ),
        risk_preferences=SupplierProfileRiskPreferences(
            tolerance=None,
            require_certificates=None,
            risky_categories=risky_categories,
            forbidden_categories=forbidden_categories,
        ),
        metadata=metadata,
    )
