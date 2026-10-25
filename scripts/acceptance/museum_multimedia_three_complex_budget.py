"""Offline illustrative risk scenarios based on first-party museum exhibit SOW.

Data are NOT vendor quotes; cash cost rates and shadow labor values are explicitly
hypothetical and fail closed to NEEDS_OWNER_CONFIRMATION regardless of margin.
No network, DB, UI, offer generation or ETP interactions.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SOURCE_NUMBER = "0161600001326000063"
NMC_RUB = Decimal(1600000)
ASSUMED_USN_REVENUE_RATE = Decimal("0.06")
PERFORMANCE_SECURITY_CONTRACT_RATE = Decimal("0.05")
# Original EIS EF2020 v1 XML applicationGuarantee/amount: separate from performance.
# Receipt docs/roadmap/b2b_44fz_two_original_bid_securities_2026-10-17.json
SOURCE_ORIGINAL_BID_APPLICATION_GUARANTEE_RUB = Decimal("16000.00")
PRICE_DISCOUNTS = ("0", "0.10", "0.20", "0.25")
_SCENARIOS = (
    ("lean_remote_unconfirmed", {
        "content_rights_digitization": 60_000, "ux_design_three_exhibits": 80_000,
        "hardware_and_acceptance_testing": 25_000, "travel_and_site_visit": 0,
        "licenses_and_ip_clearance": 30_000, "twelve_month_support_reserve": 50_000,
        "risk_contingency_cash": 50_000,
    }, 500, 1_200),
    ("baseline_one_site_visit_unconfirmed", {
        "content_rights_digitization": 140_000, "ux_design_three_exhibits": 120_000,
        "hardware_and_acceptance_testing": 65_000, "travel_and_site_visit": 150_000,
        "licenses_and_ip_clearance": 70_000, "twelve_month_support_reserve": 120_000,
        "risk_contingency_cash": 100_000,
    }, 700, 1_200),
    ("stress_remote_is_not_accepted_unconfirmed", {
        "content_rights_digitization": 220_000, "ux_design_three_exhibits": 180_000,
        "hardware_and_acceptance_testing": 120_000, "travel_and_site_visit": 350_000,
        "licenses_and_ip_clearance": 120_000, "twelve_month_support_reserve": 200_000,
        "risk_contingency_cash": 160_000,
    }, 1_000, 1_500),
)


def rub(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class CostScenario:
    name: str
    cash_categories: dict[str, int]
    internal_hours: int
    shadow_rub_per_hour: int

    def __post_init__(self) -> None:
        if len(self.cash_categories) != 7:
            raise ValueError("Scenario must identify all seven distinct cash cost categories")
        if any(not isinstance(v, int) or v < 0 for v in self.cash_categories.values()):
            raise ValueError("Cash assumptions must be nonnegative integer rubles")
        if self.internal_hours <= 0 or self.shadow_rub_per_hour <= 0:
            raise ValueError("Own labor opportunity costs cannot be hidden by zero/negative rate")

    def evaluate(self, *, bid_discount: Decimal) -> dict[str, object]:
        if not Decimal(0) <= bid_discount <= Decimal("0.25"):
            raise ValueError("Illustrative bid discount must be in 0-25% bounded range")
        bid = (NMC_RUB * (Decimal(1) - bid_discount)).quantize(Decimal(".01"))
        cash = sum((Decimal(x) for x in self.cash_categories.values()), Decimal(0))
        shadow = Decimal(self.internal_hours * self.shadow_rub_per_hour)
        tax = (bid * ASSUMED_USN_REVENUE_RATE).quantize(Decimal(".01"))
        security = (bid * PERFORMANCE_SECURITY_CONTRACT_RATE).quantize(Decimal(".01"))
        # Security ties up liquidity if posted in cash. It is NOT an expense.
        economic_profit = bid - cash - shadow - tax
        cash_left_before_shadow = bid - cash - tax
        assumed_liquidity = cash + security
        bid_phase_liquidity = SOURCE_ORIGINAL_BID_APPLICATION_GUARANTEE_RUB
        # Distinct phases: security cannot be counted as economic cash expense.
        breakeven = (cash + shadow) / (Decimal(1) - ASSUMED_USN_REVENUE_RATE)
        # Never infer statutory GO from illustrative positive margin.
        return {
            "price_discount_percent": rub(bid_discount * 100),
            "assumed_bid_price_rub": rub(bid),
            "cash_external_illustrative_rub": rub(cash),
            "own_labor_hours_assumed": self.internal_hours,
            "shadow_rate_assumed_rub_hour": self.shadow_rub_per_hour,
            "shadow_own_labor_economic_cost_rub": rub(shadow),
            "usn_six_percent_gross_planning_tax_rub": rub(tax),
            "liquidity_performance_security_5pct_rub": rub(security),
            "source_application_security_bid_phase_rub": rub(bid_phase_liquidity),
            "different_security_phases_not_summed_as_cost_or_required_concurrent_cash": True,
            "approx_upfront_cash_plus_security_upper_bound_rub": rub(assumed_liquidity),
            "cash_after_illustrative_external_cost_and_usn_before_labor_rub": rub(cash_left_before_shadow),
            "economic_profit_after_shadow_labor_and_usn_rub": rub(economic_profit),
            "economic_margin_percent": rub(economic_profit / bid * 100),
            "economic_break_even_price_rub": rub(breakeven),
            "at_or_above_25pct_discount_extra_antidumping_review": bid_discount >= Decimal(".25"),
            "owner_commercial_go": False,
            "owner_legal_go": False,
            "eligible_to_submit": False,
        }


def build() -> dict[str, object]:
    items = []
    for name, budget, hours, rate in _SCENARIOS:
        scenario = CostScenario(name, budget, hours, rate)
        rows = [scenario.evaluate(bid_discount=Decimal(d)) for d in PRICE_DISCOUNTS]
        items.append({
            "scenario_id": name,
            "assumption_basis": "AUTHOR_HYPOTHESIS_NOT_PROVIDER_QUOTE_NOT_SOURCE_COST",
            "cash_budget_hypothetical_rub": budget,
            "internal_own_labor_estimate_not_external_payment_hours": hours,
            "internal_own_labor_shadow_rate_not_a_quote_rub_per_hour": rate,
            "price_variants": rows,
        })
    return {
        "schema_version": "arvectum-three-exhibit-museum-cost-sensitivity-v1",
        "as_of": "2026-10-17",
        "source_original_44fz_notice_number": SOURCE_NUMBER,
        "source_nmck_rub": rub(NMC_RUB),
        "source_museum_interactive_programs_count": 3,
        "source_contract_completion_by": "2026-12-20",
        "source_warranty_months": 12,
        "source_execution_security_percent_of_FINAL_CONTRACT_PRICE": rub(PERFORMANCE_SECURITY_CONTRACT_RATE * 100),
        "source_official_original_application_security_rub": rub(SOURCE_ORIGINAL_BID_APPLICATION_GUARANTEE_RUB),
        "application_security_is_not_expense_and_may_have_independent_guarantee_option": True,
        "security_instruments_timings_require_owner_review": True,
        "source_payout_terms": "within 7 working days after signed acceptance (per archived contract)",
        "source_contract_status": "ARCHIVED_EF2020_V1_NOT_CURRENT_LEGAL_STATUS",
        "source_original_attachment_sha_verified": True,
        "costs_from_customer_or_vendors_verified": False,
        "travel_will_be_required_verified": False,
        "testing_remote_permitted_verified": False,
        "content_author_copyright_cleared": False,
        "tax_assumption_usn_income_six_percent_not_final_statutory_calculation": True,
        "vat_treatment_legally_verified": False,
        "payment_stages_confirmed": False,
        "bid_authorization": False,
        "does_not_submit_bid": True,
        "source_quote_binding": "docs/roadmap/b2b_priority_eis_documents_2026-10-17.json",
        "source_decision_matrix": "docs/roadmap/b2b_priority_three_matrix_2026-10-17.json",
        "scenarios": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.name != "b2b_museum_three_exhibits_cost_sensitivity_2026-10-17.json":
        parser.error("only fixed dated artifact basename permitted")
    content = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("COST_SENSITIVITY_CREATED", len(content["scenarios"]), "scenarios",
          sum(len(row["price_variants"]) for row in content["scenarios"]), "price rows",
          "BID_AUTHORIZATION", content["bid_authorization"])


if __name__ == "__main__":
    main()
