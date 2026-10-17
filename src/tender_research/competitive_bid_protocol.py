"""PRICE-01: source-bound *one-procedure* competitive bid facts, not a price forecast.

Historical NMCK/analogue normalization is already handled by ARV-057.
This module adds admitted-only final-protocol competitive bids and optional
explicit, independently provided costs. No quote, DB mutation or procurement I/O.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any

AKSAY = "0158300034526000388"
AKSAY_ZIP_SHA256 = "d25187191599e705427676cc9de64ce665029381efa2490607d65ff237837bb8"
CENTS = Decimal("0.01")
_STATUSES = {"admitted", "rejected"}


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("monetary value missing or invalid")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("monetary value invalid") from exc
    if not result.is_finite() or (positive and result <= 0) or result < 0:
        raise ValueError("monetary value must be finite and nonnegative")
    if result != result.quantize(CENTS):
        raise ValueError("monetary precision beyond kopecks")
    return result


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("invalid positive count/rank")
    return value


def _text(value: object) -> str:
    return str(value or "").strip()


def build_aksay_baseline(*, statistics_bytes: bytes, csv_bytes: bytes,
                         official_archive_sha256: str) -> dict[str, Any]:
    """Check two existing exports against pinned official-archive identity.

    Archive bytes and official XML internals are verified separately by the
    pre-existing official EIS final-protocol validator. No fresh XML implied.
    """
    if official_archive_sha256 != AKSAY_ZIP_SHA256:
        raise ValueError("unrecognized original EIS archive identity")
    if len(statistics_bytes) > 1_000_000 or len(csv_bytes) > 1_000_000:
        raise ValueError("unbounded source export")
    try:
        raw = json.loads(statistics_bytes)
        summary = raw["summary"]
        bids = raw["bids"]
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"), newline=""))
        header = reader.fieldnames
        columns = [
            "application_id", "price_rub", "status", "rank",
            "rejection_reason_code", "rejection_reason_original",
        ]
        if header != columns:
            raise ValueError("unexpected CSV bid columns")
        csv_rows = list(reader)
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, csv.Error) as exc:
        raise ValueError("malformed source bid export") from exc
    if not isinstance(summary, dict) or not isinstance(bids, list):
        raise TypeError("malformed statistics object")
    if _text(summary.get("procurement_number")) != AKSAY or summary.get("protocol_date") != "2026-10-14":
        raise ValueError("original source case or date mismatch")
    if len(bids) != _positive_int(summary.get("applications_total")) or len(csv_rows) != len(bids):
        raise ValueError("source bid count mismatches")
    if len(bids) != 55:
        raise ValueError("unexpected source original application count")
    nmck = _decimal(summary.get("nmck_rub"), positive=True)

    csv_by_id = {}
    for row in csv_rows:
        identity = _text(row.get("application_id"))
        if not identity or identity in csv_by_id:
            raise ValueError("blank or duplicate CSV application ID")
        csv_by_id[identity] = row

    ids = set()
    admitted = []
    rejected_reasons = Counter()
    observed = {}
    for row in bids:
        if not isinstance(row, dict):
            raise TypeError("non-object bid row")
        identity = _text(row.get("application_id"))
        if not identity or identity in ids or identity not in csv_by_id:
            raise ValueError("duplicate/missing original application ID")
        ids.add(identity)
        csv_row = csv_by_id[identity]
        status = row.get("status")
        if status not in _STATUSES or status != csv_row["status"]:
            raise ValueError("bid admissibility status mismatch")
        price = _decimal(row.get("price_rub"), positive=True)
        if price != _decimal(csv_row["price_rub"], positive=True):
            raise ValueError("bid price differs between JSON and CSV")
        rank = row.get("rank")
        csv_rank = _text(csv_row.get("rank"))
        if status == "admitted":
            if _positive_int(rank) != int(csv_rank or "0"):
                raise ValueError("admitted official rank mismatch")
            if row.get("rejection_reason_code") or row.get("rejection_reason_original"):
                raise ValueError("admitted bid carries rejection reason")
            admitted.append((rank, price, identity))
        elif rank is not None or csv_rank:
            raise ValueError("rejected bid cannot have an admitted rank")
        for field in ("rejection_reason_code", "rejection_reason_original"):
            if _text(row.get(field)) != _text(csv_row.get(field)):
                raise ValueError("original rejection evidence mismatch")
        if status == "rejected":
            reason = _text(row.get("rejection_reason_code"))
            if not reason:
                raise ValueError("rejected bid without source reason code")
            rejected_reasons[reason] += 1
        observed[identity] = (status, price, rank)
    if len(ids) != len(csv_by_id) or len(admitted) != _positive_int(summary.get("applications_admitted")):
        raise ValueError("admitted/unique application counts mismatch")
    rejected_count = len(bids) - len(admitted)
    if rejected_count != _positive_int(summary.get("applications_rejected")):
        raise ValueError("rejected count mismatch")
    if dict(rejected_reasons) != summary.get("rejection_causes"):
        raise ValueError("rejection cause totals mismatch")
    admitted.sort(key=lambda row: row[0])
    if [row[0] for row in admitted] != list(range(1, len(admitted) + 1)):
        raise ValueError("non-contiguous admitted official ranking")
    prices = [x[1] for x in admitted]
    if prices != sorted(prices):
        raise ValueError("rank is inconsistent with the admitted price order")
    winner_id = _text(summary.get("winner_application_id"))
    our_id = _text(summary.get("our_application_id"))
    if not winner_id or not our_id or winner_id == our_id:
        raise ValueError("unsupported winner/own source identity")
    if observed.get(winner_id) != ("admitted", _decimal(summary.get("winner_price_rub")), 1):
        raise ValueError("winner source price/rank mismatch")
    our_status, our_price, our_rank = observed.get(our_id, (None, None, None))
    if (our_status, our_price, our_rank) != (
        summary.get("our_status"), _decimal(summary.get("our_price_rub")), summary.get("our_rank")
    ) or our_status != "admitted":
        raise ValueError("company bid source proof mismatch")
    count = len(prices)
    median = (prices[(count - 1) // 2] + prices[count // 2]) / 2
    if median != _decimal(summary.get("median_admitted_rub")):
        raise ValueError("source admitted median inconsistent")
    if prices[0] != _decimal(summary.get("min_admitted_rub")) or prices[-1] != _decimal(summary.get("max_admitted_rub")):
        raise ValueError("source price min/max inconsistent")
    return {
        "schema_version": "ta-price01-protocol-one-procedure-v1",
        "procurement_number": AKSAY,
        "protocol_date": summary["protocol_date"],
        "original_eis_zip_sha256": official_archive_sha256,
        "statistics_json_sha256": hashlib.sha256(statistics_bytes).hexdigest(),
        "bids_csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "original_records_consistent": True,
        "currency": "RUB",
        "nmck_rub": str(nmck),
        "bids_total": len(bids),
        "admitted_count": len(admitted),
        "rejected_count": rejected_count,
        "rejection_reason_counts": dict(sorted(rejected_reasons.items())),
        "admitted_bid_prices_rub": {
            "min": str(prices[0]),
            "q1_nearest_rank": str(prices[(count - 1) // 4]),
            "median": str(median),
            "q3_nearest_rank": str(prices[3 * (count - 1) // 4]),
            "max": str(prices[-1]),
        },
        "winner": {"application_id": winner_id, "rank": 1, "price_rub": str(prices[0])},
        "arvectum_bid": {
            "application_id": our_id, "rank": our_rank, "price_rub": str(our_price),
            "admitted": True, "admitted_offers_with_lower_price": sum(p < our_price for p in prices),
        },
        "comparable_distinct_procurements": 1,
        "cross_procurement_price_evidence": "INSUFFICIENT_EVIDENCE",
        "cost_break_even_scenarios": None,
        "cost_inputs_required": True,
        "is_win_probability_forecast": False,
        "is_bid_recommendation": False,
        "submission_or_payment_performed": False,
    }


def compute_owner_supplied_break_even(
    *, external_direct_rub: object, labor_rub: object, reserve_rub: object,
    fixed_platform_fees_rub: object, revenue_tax_rate: object,
    variable_platform_fee_rate: object, target_profit_rub: object,
) -> dict[str, str]:
    """Only explicit independent inputs; no default user/company cost assumptions.

    Revenue tax/fees are *scenario assumptions*, not verified tax advice.
    Do not use output as an authorized participation/bid or price recommendation.
    """
    fixed = sum((
        _decimal(external_direct_rub), _decimal(reserve_rub),
        _decimal(fixed_platform_fees_rub)
    ), start=Decimal(0))
    labor = _decimal(labor_rub)
    target = _decimal(target_profit_rub)
    try:
        tax = Decimal(str(revenue_tax_rate))
        fee = Decimal(str(variable_platform_fee_rate))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid explicit revenue rate") from exc
    if any(not r.is_finite() or r < 0 or r >= 1 for r in (tax, fee)):
        raise ValueError("invalid percentage")
    divisor = 1 - tax - fee
    if divisor <= 0:
        raise ValueError("fees consume all revenue")
    def break_even(cost: Decimal) -> str:
        return str((cost / divisor).quantize(CENTS, rounding=ROUND_CEILING))
    return {
        "cash_cost_break_even_rub": break_even(fixed),
        "full_economic_break_even_rub": break_even(fixed + labor),
        "full_cost_plus_explicit_target_rub": break_even(fixed + labor + target),
        "assumptions": "EXPLICIT_OWNER_INPUT_ONLY_NOT_A_BID",
        "is_bid_recommendation": "false",
    }
