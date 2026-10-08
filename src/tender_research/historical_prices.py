from __future__ import annotations

import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field

from src.modules.price_normalization.normalize import normalize_price, normalize_title
from src.tender_research.models import ProcurementTender
from src.tender_research.repository import TenderRepository
from src.tender_research.similar_procurements import (
    SimilarProcurementItem,
    find_similar_procurements,
)

PriceBasis = Literal["SINGLE_POSITION_UNIT_NMCK", "MATCHED_BASKET_TOTAL_NMCK"]
RangeState = Literal["AVAILABLE", "INSUFFICIENT_EVIDENCE"]
Orientation = Literal["BELOW_RANGE", "WITHIN_RANGE", "ABOVE_RANGE", "UNKNOWN"]

_POSITION_CONTAINER_KEYS = {
    "positions",
    "items",
    "purchase_objects",
    "purchaseobjects",
    "products",
    "goods",
}
_NAME_KEYS = (
    "name",
    "item_name",
    "product_name",
    "title",
    "description",
    "object_name",
)
_QUANTITY_KEYS = ("quantity", "qty", "volume")
_UNIT_KEYS = ("unit", "unit_name", "okei_name", "measure", "measure_unit")
_MIN_POSITION_OVERLAP = Decimal("0.20")
_MIN_SUBJECT_OVERLAP_WITHOUT_POSITION_SIGNAL = Decimal("0.40")
_MIN_COMPARABLE_SAMPLES = 2
_MONEY_QUANT = Decimal("0.01")


class HistoricalPriceEvidence(BaseModel):
    source_type: str
    source_ref: str
    source_url: str | None = None
    quote: str | None = None


class HistoricalPriceObservation(BaseModel):
    tender_id: str
    registry_number: str | None = None
    publication_date: str
    title: str
    amount: float
    currency: str
    basis: PriceBasis
    unit: str | None = None
    source_nmck_amount: float
    quantity: float | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)
    comparability_reasons: list[str] = Field(default_factory=list)
    evidence: list[HistoricalPriceEvidence] = Field(default_factory=list)


class HistoricalPriceRange(BaseModel):
    minimum: float
    median: float
    maximum: float
    currency: str
    basis: PriceBasis
    unit: str | None = None
    sample_count: int


class HistoricalPriceResponse(BaseModel):
    seed_tender_id: str
    seed_registry_number: str | None = None
    seed_title: str
    state: RangeState
    range: HistoricalPriceRange | None = None
    seed_orientation: Orientation = "UNKNOWN"
    seed_comparable_amount: float | None = None
    observations: list[HistoricalPriceObservation] = Field(default_factory=list)
    seed_evidence: list[HistoricalPriceEvidence] = Field(default_factory=list)
    rejected_counts: dict[str, int] = Field(default_factory=dict)
    comparability_policy: list[str] = Field(
        default_factory=lambda: [
            "candidate_must_be_earlier_than_seed",
            "currency_must_match_exactly",
            "candidate_must_pass_ARV-055_false_analogue_guards",
            "structured_position_overlap_must_be_at_least_0.20_when_available",
            "subject_overlap_must_be_at_least_0.40_when_position_signal_is_unavailable",
            "single_position_ranges_are_normalized_as_nmck_per_quantity_with_matching_units",
            "multi_position_total_nmck_requires_exact_quantity_and_unit_basket_match",
            "at_least_two_comparable_observations_are_required",
        ]
    )
    is_forecast: bool = False
    commercial_commitment: bool = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Historical observations are source-bound facts, not a forecast of winning price, participant count, or final contract price.",
            "The range is an orientation aid only and does not recommend a bid, participation decision, or commercial commitment.",
        ]
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def _normal_unit(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    aliases = {
        "шт.": "шт",
        "штука": "шт",
        "штук": "шт",
        "ед.": "ед",
        "единица": "ед",
        "кг.": "кг",
        "л.": "л",
        "м.": "м",
        "компл.": "комплект",
    }
    return aliases.get(text, text)


def _walk_position_rows(value: object, *, depth: int = 0) -> list[dict]:
    if depth > 5:
        return []
    rows: list[dict] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_norm = str(key).replace("-", "_").casefold()
            if key_norm in _POSITION_CONTAINER_KEYS and isinstance(nested, list):
                rows.extend(row for row in nested[:50] if isinstance(row, dict))
            rows.extend(_walk_position_rows(nested, depth=depth + 1))
    elif isinstance(value, list):
        for nested in value[:50]:
            rows.extend(_walk_position_rows(nested, depth=depth + 1))
    return rows


def _first_value(row: dict, keys: tuple[str, ...]) -> object | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _position_signature(
    tender: ProcurementTender,
) -> list[tuple[str, Decimal, str]]:
    raw = tender.raw_payload
    if not isinstance(raw, (dict, list)):
        return []
    result: list[tuple[str, Decimal, str]] = []
    seen: set[tuple[str, Decimal, str]] = set()
    for row in _walk_position_rows(raw):
        quantity = normalize_price(_first_value(row, _QUANTITY_KEYS))
        unit = _normal_unit(_first_value(row, _UNIT_KEYS))
        if quantity is None or quantity <= 0 or not unit:
            continue
        name = normalize_title(str(_first_value(row, _NAME_KEYS) or ""))
        item = (name, quantity, unit)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result[:50]


def _signal_score(item: SimilarProcurementItem, name: str) -> Decimal | None:
    for signal in item.signals:
        if signal.signal == name and signal.available and signal.score is not None:
            return Decimal(str(signal.score))
    return None


def _currency(value: str | None) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _basket_signature(
    rows: list[tuple[str, Decimal, str]],
) -> Counter[tuple[str, Decimal, str]]:
    return Counter((name, quantity, unit) for name, quantity, unit in rows)


def _basis_for_pair(
    seed: ProcurementTender,
    candidate: ProcurementTender,
) -> tuple[PriceBasis, Decimal, Decimal | None, str | None, str] | None:
    seed_nmck = normalize_price(seed.nmck_amount)
    candidate_nmck = normalize_price(candidate.nmck_amount)
    if candidate_nmck is None or candidate_nmck <= 0:
        return None

    seed_rows = _position_signature(seed)
    candidate_rows = _position_signature(candidate)
    if len(seed_rows) == 1 and len(candidate_rows) == 1:
        _seed_name, seed_qty, seed_unit = seed_rows[0]
        _candidate_name, candidate_qty, candidate_unit = candidate_rows[0]
        if seed_unit != candidate_unit:
            return None
        candidate_amount = candidate_nmck / candidate_qty
        seed_amount = (
            (seed_nmck / seed_qty) if seed_nmck is not None and seed_nmck > 0 else None
        )
        return (
            "SINGLE_POSITION_UNIT_NMCK",
            _money(candidate_amount),
            _money(seed_amount) if seed_amount is not None else None,
            seed_unit,
            f"single-position NMCK normalized per {seed_unit}; quantities seed={seed_qty} candidate={candidate_qty}",
        )

    if (
        len(seed_rows) > 1
        and len(candidate_rows) > 1
        and len(seed_rows) == len(candidate_rows)
        and _basket_signature(seed_rows) == _basket_signature(candidate_rows)
    ):
        return (
            "MATCHED_BASKET_TOTAL_NMCK",
            _money(candidate_nmck),
            _money(seed_nmck) if seed_nmck is not None and seed_nmck > 0 else None,
            None,
            "multi-position total NMCK with exact quantity/unit basket match",
        )
    return None


def _source_evidence(tender: ProcurementTender) -> list[HistoricalPriceEvidence]:
    source_ref = tender.registry_number or tender.external_id
    url = tender.eis_url or tender.platform_url
    evidence = [
        HistoricalPriceEvidence(
            source_type="PROCUREMENT_TENDER_SUBJECT",
            source_ref=f"{tender.source}:{source_ref}:title",
            source_url=url,
            quote=tender.title,
        )
    ]
    if tender.nmck_amount is not None:
        evidence.append(
            HistoricalPriceEvidence(
                source_type="PROCUREMENT_TENDER_NMCK",
                source_ref=f"{tender.source}:{source_ref}:nmck_amount",
                source_url=url,
                quote=f"NMCK={tender.nmck_amount} {tender.currency or ''}".strip(),
            )
        )
    if tender.publication_date is not None:
        evidence.append(
            HistoricalPriceEvidence(
                source_type="PROCUREMENT_TENDER_PUBLICATION",
                source_ref=f"{tender.source}:{source_ref}:publication_date",
                source_url=url,
                quote=tender.publication_date.isoformat(),
            )
        )
    positions = _position_signature(tender)
    if positions:
        evidence.append(
            HistoricalPriceEvidence(
                source_type="PROCUREMENT_TENDER_POSITION_BASIS",
                source_ref=f"{tender.source}:{source_ref}:structured_position_basis",
                source_url=url,
                quote="; ".join(
                    f"{name or '<unnamed>'} | quantity={quantity} | unit={unit}"
                    for name, quantity, unit in positions
                )[:1200],
            )
        )
    return evidence


def build_historical_price_range(
    repo: TenderRepository,
    retriever,
    *,
    registry_number: str,
    observation_limit: int = 10,
) -> HistoricalPriceResponse | None:
    seed = repo.get_tender_by_registry_number(registry_number)
    if seed is None:
        return None

    rejected: Counter[str] = Counter()
    if seed.publication_date is None:
        rejected["seed_publication_date_unknown"] += 1
        return HistoricalPriceResponse(
            seed_tender_id=str(seed.id),
            seed_registry_number=seed.registry_number,
            seed_title=seed.title,
            seed_evidence=_source_evidence(seed),
            state="INSUFFICIENT_EVIDENCE",
            rejected_counts=dict(rejected),
        )
    seed_currency = _currency(seed.currency)
    if seed_currency is None:
        rejected["seed_currency_unknown"] += 1
        return HistoricalPriceResponse(
            seed_tender_id=str(seed.id),
            seed_registry_number=seed.registry_number,
            seed_title=seed.title,
            seed_evidence=_source_evidence(seed),
            state="INSUFFICIENT_EVIDENCE",
            rejected_counts=dict(rejected),
        )
    if not _position_signature(seed):
        rejected["seed_quantity_or_unit_unknown"] += 1
        return HistoricalPriceResponse(
            seed_tender_id=str(seed.id),
            seed_registry_number=seed.registry_number,
            seed_title=seed.title,
            seed_evidence=_source_evidence(seed),
            state="INSUFFICIENT_EVIDENCE",
            rejected_counts=dict(rejected),
        )

    similar = find_similar_procurements(
        repo,
        retriever,
        registry_number=registry_number,
        limit=min(50, max(20, observation_limit * 5)),
    )
    if similar is None:
        return None

    observations: list[HistoricalPriceObservation] = []
    observed_basis: PriceBasis | None = None
    observed_unit: str | None = None
    seed_comparable_amount: Decimal | None = None

    for item in similar.items:
        candidate = repo.get_tender_by_id(item.tender_id)
        if candidate is None:
            rejected["candidate_missing"] += 1
            continue
        if candidate.publication_date is None:
            rejected["candidate_publication_date_unknown"] += 1
            continue
        if candidate.publication_date >= seed.publication_date:
            rejected["not_historical"] += 1
            continue
        candidate_currency = _currency(candidate.currency)
        if candidate_currency != seed_currency:
            rejected["currency_mismatch_or_unknown"] += 1
            continue

        position_score = _signal_score(item, "positions")
        subject_score = _signal_score(item, "subject")
        if position_score is not None:
            if position_score < _MIN_POSITION_OVERLAP:
                rejected["position_overlap_too_low"] += 1
                continue
            overlap_reason = f"structured position overlap={position_score}"
        else:
            if (
                subject_score is None
                or subject_score < _MIN_SUBJECT_OVERLAP_WITHOUT_POSITION_SIGNAL
            ):
                rejected["subject_overlap_too_low_without_positions"] += 1
                continue
            overlap_reason = (
                f"subject overlap={subject_score} with position signal unavailable"
            )

        basis = _basis_for_pair(seed, candidate)
        if basis is None:
            rejected["quantity_unit_basis_incomparable"] += 1
            continue
        basis_name, amount, candidate_seed_amount, unit, basis_reason = basis
        if observed_basis is None:
            observed_basis = basis_name
            observed_unit = unit
            seed_comparable_amount = candidate_seed_amount
        elif basis_name != observed_basis or unit != observed_unit:
            rejected["mixed_price_basis"] += 1
            continue

        observations.append(
            HistoricalPriceObservation(
                tender_id=str(candidate.id),
                registry_number=candidate.registry_number,
                publication_date=candidate.publication_date.isoformat(),
                title=candidate.title,
                amount=float(amount),
                currency=seed_currency,
                basis=basis_name,
                unit=unit,
                source_nmck_amount=float(candidate.nmck_amount),
                quantity=float(_position_signature(candidate)[0][1])
                if basis_name == "SINGLE_POSITION_UNIT_NMCK"
                else None,
                similarity_score=item.similarity_score,
                comparability_reasons=[
                    "candidate publication predates seed",
                    f"currency={seed_currency}",
                    overlap_reason,
                    basis_reason,
                ],
                evidence=_source_evidence(candidate),
            )
        )

    observations.sort(
        key=lambda item: (
            item.publication_date,
            item.registry_number or "",
            item.tender_id,
        ),
        reverse=True,
    )
    observations = observations[:observation_limit]

    if len(observations) < _MIN_COMPARABLE_SAMPLES or observed_basis is None:
        if len(observations) < _MIN_COMPARABLE_SAMPLES:
            rejected["insufficient_comparable_samples"] += 1
        return HistoricalPriceResponse(
            seed_tender_id=str(seed.id),
            seed_registry_number=seed.registry_number,
            seed_title=seed.title,
            seed_evidence=_source_evidence(seed),
            state="INSUFFICIENT_EVIDENCE",
            seed_comparable_amount=float(seed_comparable_amount)
            if seed_comparable_amount is not None
            else None,
            observations=observations,
            rejected_counts=dict(rejected),
        )

    values = [Decimal(str(item.amount)) for item in observations]
    min_value = _money(min(values))
    median_value = _money(Decimal(str(median(values))))
    max_value = _money(max(values))
    orientation: Orientation = "UNKNOWN"
    if seed_comparable_amount is not None:
        if seed_comparable_amount < min_value:
            orientation = "BELOW_RANGE"
        elif seed_comparable_amount > max_value:
            orientation = "ABOVE_RANGE"
        else:
            orientation = "WITHIN_RANGE"

    return HistoricalPriceResponse(
        seed_tender_id=str(seed.id),
        seed_registry_number=seed.registry_number,
        seed_title=seed.title,
        seed_evidence=_source_evidence(seed),
        state="AVAILABLE",
        range=HistoricalPriceRange(
            minimum=float(min_value),
            median=float(median_value),
            maximum=float(max_value),
            currency=seed_currency,
            basis=observed_basis,
            unit=observed_unit,
            sample_count=len(observations),
        ),
        seed_orientation=orientation,
        seed_comparable_amount=float(seed_comparable_amount)
        if seed_comparable_amount is not None
        else None,
        observations=observations,
        rejected_counts=dict(rejected),
    )
