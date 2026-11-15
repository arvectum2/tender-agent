"""Evidence-bound retrospective auction economics; no external actions."""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from src.modules.tender_connectors.mos_portal.public_auction import detail_row, list_row

CENT = Decimal("0.01")


def amount(value):
    if value is None or isinstance(value, bool):
        raise ValueError("required monetary amount")
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError("nonfinite or negative amount")
    return d


def clock(value):
    return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")  # noqa: DTZ007 - source wall-clock comparison only


def verified_bid_trace(listing, detail):
    row = detail_row(detail, list_row(listing))
    if row["state"] not in {"finished", "offers_signed"} or not row["winner"]:
        raise ValueError("historical selected candidate required")
    winner = listing["winner"]
    final = detail.get("lastBetSupplier") or {}
    if (not winner.get("supplierId") or final.get("id") != winner["supplierId"]
            or final.get("name") != winner["name"]):
        raise ValueError("winner identity mismatch between list and final detail")
    bids = sorted(detail.get("bets") or [], key=lambda b: b["num"])
    if not bids or row["offer_count"] != len(bids) or [b["num"] for b in bids] != list(range(1, len(bids)+1)):
        raise ValueError("incomplete sequence")
    if len({b["id"] for b in bids}) != len(bids):
        raise ValueError("duplicate bid identity")
    start, end = clock(detail["startDate"]), clock(detail["endDate"])
    prior_price, prior_time = amount(detail["startCost"]), start
    trace = []
    for b in bids:
        cost, when = amount(b["cost"]), clock(b["serverTime"])
        if (str(b["auctionId"]) != row["external_id"] or b.get("isBlocked") is not False
                or type(b.get("isAutoBet")) is not bool or cost >= prior_price
                or not prior_time <= when <= end):
            raise ValueError("inconsistent bid sequence or blocked bid")
        trace.append({"number": b["num"], "price_rub": str(cost),
                      "server_time_raw": b["serverTime"], "auto": b["isAutoBet"]})
        prior_price, prior_time = cost, when
    if bids[-1]["id"] != detail["lastBetId"] or prior_price != amount(row["detail_last_bid_rub"]):
        raise ValueError("last bid mismatch")
    if row["list_current_bid_rub"] is None or prior_price != amount(row["list_current_bid_rub"]):
        raise ValueError("missing independent list bid confirmation")
    count = detail.get("uniqueSupplierCount")
    if type(count) is not int or not 1 <= count <= len(trace):
        raise ValueError("invalid source participant count")
    return {"auction_id": row["external_id"], "state": row["state"],
            "observed_start_rub": row["list_initial_price_rub"],
            "observed_final_bid_rub": str(prior_price),
            "reduction_percent": str(((amount(row["list_initial_price_rub"])-prior_price)
                                       / amount(row["list_initial_price_rub"])*100).quantize(CENT)),
            "bid_count": len(trace), "automatic_bids": sum(b["auto"] for b in trace),
            "source_unique_participants": count,
            "winner_identity_cross_checked": True, "winner_inn": row["winner"]["inn"],
            "offers_signed_source_flag": detail.get("offersSigned"),
            "signed_contract_amount_rub": None, "positions": row["items"],
            "initial_position_sum_matches": row["initial_position_sum_matches"],
            "sequence": trace, "verification": "OBSERVED_PUBLIC_BID_TRACE_NOT_CONTRACT"}


def cost_ceiling(bid, *, logistics, overhead, contingency, markup, variable_revenue_fee=0, fixed=0):
    """Supplier basket ceiling for a hypothetical target markup, same tax basis."""
    revenue, logistics, overhead, contingency, markup, fee, fixed = [
        amount(x) for x in (bid, logistics, overhead, contingency, markup, variable_revenue_fee, fixed)]
    if revenue <= 0 or fee >= 1 or max(logistics, overhead, contingency, markup) > 1:
        raise ValueError("invalid scenario rates or benchmark")
    usable = (revenue*(1-fee))/(1+markup)-fixed
    ceiling = usable/(1+logistics+overhead+contingency)
    return {"benchmark_bid_rub": str(revenue),
            "max_supplier_basket_rub": str(ceiling.quantize(CENT, rounding=ROUND_DOWN)) if ceiling >= 0 else None,
            "logistics_rate_on_cost": str(logistics), "overhead_rate_on_cost": str(overhead),
            "contingency_rate_on_cost": str(contingency), "markup_on_total_cost": str(markup),
            "variable_revenue_fee_rate": str(fee), "fixed_cost_rub": str(fixed),
            "assumption_only": True, "tax_basis": "must_be_consistent_and_verified",
            "missing_actual_supplier_quotes": True, "actual_profit_rub": None,
            "trade_decision": "INSUFFICIENT_COST_EVIDENCE"}


def scenario_report(trace):
    # Existing C5 heuristic rates, used only as hypothetical sensitivity.
    return {"auction_id": trace["auction_id"], "basis": "C5 heuristic sensitivity, not historical costs",
            "scenarios": [cost_ceiling(trace["observed_final_bid_rub"], logistics="0.08",
                                       overhead="0.07", contingency=r, markup="0.12")
                          for r in ("0.03", "0.05", "0.08")],
            "benchmark_is_ex_post": True, "claims_counterfactual_win": False,
            "requires": ["time-valid matching SKU supplier quote", "quantity and stock",
                         "delivery and timing", "VAT and tax basis", "fees and required security",
                         "financing and payment timing"]}
