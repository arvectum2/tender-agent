"""Reproducible *internal* scenario economics, not a commercial bid or legal GO.

Trusted inputs: first-party pinned, archived public original receipts + explicit
person-hour/rate assumptions. No source text rewriting, external messages or ETP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "docs/roadmap/b2b_prebid_cost_assumptions_2026-10-18.json"
SOURCES = ROOT / "docs/roadmap"
SCENARIOS = ("low", "base", "high")
SHA = re.compile(r"[a-f0-9]{64}\Z")


class CostValidationError(ValueError):
    """Reject untrusted source/assumptions or misleading pricing."""


def _money(value: object) -> Decimal:
    if not isinstance(value, str):
        raise CostValidationError("monetary rate must be explicit decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise CostValidationError("invalid monetary value") from exc
    if not number.is_finite() or not 0 <= number <= 100_000_000:
        raise CostValidationError("monetary value outside bounds")
    return number


def _fraction(value: object) -> Decimal:
    fraction = _money(value)
    if fraction > 0.75:
        raise CostValidationError("tax/reserve fraction outside internal allowed bound")
    return fraction


def _rounded(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _roundup(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def _require_source(value: object, expected: str, key: str) -> None:
    if not isinstance(value, str) or not SHA.fullmatch(value) or value != expected:
        raise CostValidationError(f"source snapshot SHA mismatch: {key}")


def validate_original_references(model: dict, notices: dict, attachments: dict, commercial: dict) -> None:
    if model.get("schema_version") != "b2b_prebid_internal_cost_assumptions_v1":
        raise CostValidationError("unknown estimation input schema")
    if model.get("pricing_model") != "INTERNAL_OPPORTUNITY_COST_NOT_QUOTE":
        raise CostValidationError("attempted promotion to commercial quote")
    if not isinstance(model.get("cases"), list) or len(model["cases"]) != 2:
        raise CostValidationError("two bounded source cases required")
    if {c["id"] for c in model["cases"]} != {"0163200000326005243", "4643484"}:
        raise CostValidationError("incorrect original procurement identities")

    sm = next(c for c in model["cases"] if c["id"] == "0163200000326005243")
    bb = next(c for c in model["cases"] if c["id"] == "4643484")
    record = next((x for x in notices.get("records", []) if x.get("number") == sm["id"]), None)
    entry = next((x for x in attachments.get("entries", []) if x.get("registry_number") == sm["id"]), None)
    if not isinstance(record, dict) or not isinstance(entry, dict):
        raise CostValidationError("EIS source original not independently received")
    if (record.get("archival_evidence") != "SHA_VERIFIED_NOTICE"
            or record.get("selected_archived_version") != 2
            or record.get("current_live_legal_status_verified") is not False
            or entry.get("bid_ready") is not False):
        raise CostValidationError("not an archived EIS original / unsafe readiness")
    _require_source(sm.get("source_zip_sha256"), record.get("zip_sha256"), "smolensk_zip")
    _require_source(sm.get("source_notice_xml_sha256"), record.get("original_xml_sha256"), "smolensk_notice")
    files = {x["original_name"]: x["binary_sha256"] for x in entry.get("files", [])}
    for property_name, file_name in (
        ("source_tz_docx_sha256", "Описание объекта закупки.docx"),
        ("source_evaluation_docx_sha256", "Критерии оценки заявок и порядок рассмотрения.docx"),
        ("source_contract_docx_sha256", "Проект государственного контракта.docx"),
        ("source_application_docx_sha256", "Требования к составу заявки и инструкция по заполнению КОНКУРС.docx"),
    ):
        _require_source(sm.get(property_name), files.get(file_name), property_name)
    if (sm.get("source_contract_deadline") != "2026-12-08"
            or sm.get("source_warranty_months") != 12
            or sm.get("source_price_weight_percent") != 30
            or sm.get("source_qualification_weight_percent") != 70
            or sm.get("source_archived_application_deadline") != record.get("source_archived_end_dt")
            or _money(sm.get("public_budget_ceiling_rub")) != _money(str(record.get("source_archived_nmck_rub")))):
        raise CostValidationError("Smolensk original contract / scoring mismatch")
    if commercial.get("registry_number") != bb["id"] or commercial.get("buyer_go_or_bid_ready") is not False:
        raise CostValidationError("B2B-Center original page unbound")
    _require_source(bb.get("source_detail_html_sha256"), commercial.get("detail_html_sha256"), "b2b_detail")
    _require_source(bb.get("source_index_html_sha256"), commercial.get("index_html_sha256"), "b2b_index")
    if (bb.get("public_budget_ceiling_rub") is not None
            or bb.get("original_public_deadline") != commercial.get("original_printed_deadline_moscow")):
        raise CostValidationError("invented B2B-Center price or deadline")
    if any(c.get("owner_bid_ready") is not False for c in model["cases"]):
        raise CostValidationError("commercial or legal GO cannot be asserted")


def calculate(model: dict, notices: dict, attachments: dict, commercial: dict) -> dict:
    validate_original_references(model, notices, attachments, commercial)
    rates = model.get("roles")
    if not isinstance(rates, dict) or not rates:
        raise CostValidationError("internal role valuation missing")
    roles = {name: _money(meta["scenario_rate_rub_per_hour"]) for name, meta in rates.items()}
    if any(rate <= 0 for rate in roles.values()):
        raise CostValidationError("zero/negative opportunity-cost rate not accepted")
    tax = _fraction(model["assumptions_not_from_buyer"]["tax_fraction_of_collected_revenue"])
    reserve = model["scenario_contingency_fraction"]
    cash = model["scenario_other_cash_cost_rub"]
    if set(reserve) != set(SCENARIOS) or set(cash) != set(SCENARIOS):
        raise CostValidationError("incomplete three-point assumptions")
    case_results = []
    for c in model["cases"]:
        tasks = c.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise CostValidationError("work package list missing")
        if len({t.get("id") for t in tasks}) != len(tasks):
            raise CostValidationError("duplicate work package")
        if not isinstance(c.get("blocking_unknowns"), list) or not c["blocking_unknowns"]:
            raise CostValidationError("missing buyer/owner blocking questions")
        for t in tasks:
            scope = t.get("source_scope")
            if (
                not isinstance(scope, str)
                or scope not in {"source_tz", "source_contract_5_1", "assumption_unprovided_scope"}
                or (c["id"] == "4643484" and scope != "assumption_unprovided_scope")
                or (c["id"] == "0163200000326005243" and scope == "assumption_unprovided_scope")
                or (scope == "source_tz" and not t.get("tz_paragraph_refs"))
            ):
                raise CostValidationError("unattributed source vs proposal package")
            if t.get("role") not in roles or set(t.get("hours", {})) != set(SCENARIOS):
                raise CostValidationError("role or three point hours missing")
            h = [t["hours"][s] for s in SCENARIOS]
            if any(type(x) is not int or x < 0 or x > 1000 for x in h) or h != sorted(h):
                raise CostValidationError("hours not bounded low <= base <= high")
        scenario_results = {}
        for scenario in SCENARIOS:
            work = sum((Decimal(t["hours"][scenario]) * roles[t["role"]] for t in tasks), Decimal(0))
            hours = sum(t["hours"][scenario] for t in tasks)
            buffer = (work * _fraction(reserve[scenario]))
            other = _money(cash[scenario])
            valued_total = work + buffer + other
            required_revenue = valued_total / (Decimal(1) - tax)
            price = c.get("public_budget_ceiling_rub")
            max_rev = _money(price) if price is not None else None
            scenario_results[scenario] = {
                "hours_total": hours,
                "imputed_labor_opportunity_cost_rub": _rounded(work),
                "risk_allowance_rub": _rounded(buffer),
                "assumed_other_cash_cost_rub": _rounded(other),
                "estimated_total_economic_cost_rub": _rounded(valued_total),
                "hypothetical_revenue_to_cover_imputed_costs_rub": _roundup(required_revenue),
                "published_budget_ceiling_rub": _rounded(max_rev) if max_rev is not None else None,
                "headroom_at_published_ceiling_after_assumed_tax_and_cost_rub": (
                    _rounded(max_rev * (Decimal(1) - tax) - valued_total)
                    if max_rev is not None else None
                ),
                "cash_before_labor_at_published_ceiling_rub": (
                    _rounded(max_rev * (Decimal(1) - tax) - other)
                    if max_rev is not None else None
                ),
                "owner_approval_for_price": False,
                "offer_sent": False,
            }
        if not (
            scenario_results["low"]["hours_total"]
            <= scenario_results["base"]["hours_total"]
            <= scenario_results["high"]["hours_total"]
        ):
            raise CostValidationError("non-monotone effort scenarios")
        case_results.append({
            "id": c["id"],
            "source_kind": c["source_kind"],
            "source_revision_is_current_verified": False,
            "full_scope_is_confirmed": False,
            "owner_legal_and_commercial_bid_go": False,
            "work_package_count": len(tasks),
            "blocking_unknowns": c["blocking_unknowns"],
            "scenarios": scenario_results,
        })
    return {
        "contract_version": "b2b_internal_prebid_opportunity_cost_v1",
        "status": "REPRODUCIBLE_INTERNAL_ASSUMPTIONS_NOT_CUSTOMER_PRICE",
        "assumed_role_rates_not_market_facts": True,
        "tax_fraction_is_scenario_not_tax_advice": str(tax),
        "source_archived_legal_currentness_confirmed": False,
        "contract_bid_authorized": False,
        "external_communications_count": 0,
        "original_contract_or_tender_text_republished": False,
        "case_results": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for p in (args.input, SOURCES / "b2b_oct18_three_new_eis_originals.json",
              SOURCES / "b2b_oct18_three_official_attachments.json",
              SOURCES / "b2b_oct18_b2bcenter_4643484_firstparty.json"):
        if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= 120000:
            parser.error("source JSON missing, symbolic link or excessive")
    model = json.loads(args.input.read_text())
    source = json.loads((SOURCES / "b2b_oct18_three_new_eis_originals.json").read_text())
    docs = json.loads((SOURCES / "b2b_oct18_three_official_attachments.json").read_text())
    comm = json.loads((SOURCES / "b2b_oct18_b2bcenter_4643484_firstparty.json").read_text())
    result = calculate(model, source, docs, comm)
    result["source_assumption_input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content)
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
