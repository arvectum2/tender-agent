"""Synthetic contract tests: synthetic URLs/amounts do not describe actual RF tenders."""

from copy import deepcopy

import pytest

from src.modules.market_intelligence import (
    MarketInputError,
    analyze_market,
    render_markdown,
)


def portfolio():
    return {
        "supplier": {
            "name": "SYNTHETIC Power Quality Supplier",
            "products": [
                {"id": "statcom", "name": "СТАТКОМ", "synonyms": ["STATCOM", "SVG"]},
                {"id": "filter", "name": "Фильтр гармоник"},
            ],
        },
        "as_of": "2026-10-24",
        "window_from": "2023-10-24",
        "window_to": "2026-10-24",
        "coverage": [{"source": "synthetic_eis", "status": "partial", "notes": "test-only"}],
        "records": [],
    }


def rec(**changes):
    default = {
        "regime": "223-fz", "procurement_id": "P-100", "lot_id": "1",
        "award_id": "C-100", "external_id": "notice-100",
        "source": "synthetic_eis", "stage": "awarded", "scope": "epc",
        "event_on": "2025-10-01", "observed_on": "2026-10-23",
        "buyer": {"inn": "7707083893", "name": "SYNTHETIC Заказчик"},
        "winner": {"inn": "7710140679", "name": "SYNTHETIC EPC"},
        "project_id": "project-1", "project_name": "SYNTHETIC substation",
        "value_rub": "300000000", "price_basis": "contract", "component_value_rub": None,
        "deadline_on": "2026-11-05",
        "dedicated_lot": False, "participants": [],
        "evidence": [{
            "url": "https://example.org/synthetic/protocol/100",
            "locator": "Synthetic appendix, p.10",
            "excerpt": "ТЗ: система компенсации реактивной мощности СТАТКОМ",
            "source_type": "synthetic",
            "facts": ["buyer", "winner", "scope", "value", "price_basis:contract", "product:statcom", "deadline"],
        }],
    }
    default.update(changes)
    return default


def run(*records):
    p = portfolio()
    p["records"] = list(records)
    return analyze_market(p)


def test_epc_total_not_assumed_product_market():
    report = run(rec())
    assert report["market_size_status"] == "INSUFFICIENT_COVERAGE"
    amounts = report["observed_award_values_rub"]
    assert amounts["epc_full_envelope_not_market_size"] == "300000000"
    assert amounts["confirmed_addressable_total"] == "0"
    assert report["counts"]["awarded_relevant_without_product_price"] == 1
    assert {a["role"] for a in report["accounts"]} == {"end_customer", "epc_contractor"}
    assert "недостаточно" in render_markdown(report)


def test_explicit_component_and_dedicated_supply_are_separate():
    epc = rec(component_value_rub="5000000")
    epc["evidence"][0]["facts"].extend(["component_value", "component_basis:contract_line"])
    supply = rec(procurement_id="P-200", award_id="C-200", scope="supply",
                 value_rub="20000000", dedicated_lot=True)
    supply["evidence"][0]["facts"].append("dedicated_lot")
    report = run(epc, supply)
    v = report["observed_award_values_rub"]
    assert v["confirmed_addressable_total"] == "25000000"
    assert v["confirmed_embedded_component"] == "5000000"
    assert v["confirmed_dedicated_supply"] == "20000000"
    assert v["epc_full_envelope_not_market_size"] == "300000000"


def test_crosspost_dedup_same_award_preserves_provenance():
    first = rec()
    second = rec(source="synthetic_etp", external_id="mirror-100")
    second["evidence"][0]["url"] = "https://example.org/synthetic/etp/mirror"
    report = run(first, second)
    assert report["counts"]["deduplicated_lots_awards"] == 1
    assert report["counts"]["relevant_lots_awards"] == 1
    assert len(report["procurements"][0]["sources"]) == 2
    assert len(report["procurements"][0]["evidence"]) == 2
    assert report["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "300000000"


def test_two_contracts_same_lot_are_distinct():
    report = run(rec(award_id="C-100", component_value_rub="5000000",
                     evidence=[{**rec()["evidence"][0], "facts": ["buyer", "scope", "value", "price_basis:contract",
                              "product:statcom", "component_value", "component_basis:contract_line"]}]),
                 rec(award_id="C-101", component_value_rub="1000000",
                     evidence=[{**rec()["evidence"][0], "facts": ["buyer", "scope", "value", "price_basis:contract",
                              "product:statcom", "component_value", "component_basis:contract_line"]}]))
    assert report["counts"]["deduplicated_lots_awards"] == 2
    assert report["observed_award_values_rub"]["confirmed_addressable_total"] == "6000000"


def test_notice_shadowed_by_award_no_open_double_count():
    notice = rec(stage="open", award_id=None, observed_on="2025-09-01")
    result = run(notice, rec())
    assert result["counts"]["open_opportunities"] == 0
    assert len(result["procurements"]) == 2
    assert not any(r["is_open_opportunity"] for r in result["procurements"])


def test_open_procedure_is_opportunity_not_awarded_revenue():
    report = run(rec(stage="open", award_id=None, value_rub="300000000"))
    assert report["counts"]["open_opportunities"] == 1
    assert report["observed_award_values_rub"]["confirmed_addressable_total"] == "0"
    assert report["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "0"


def test_cancellation_with_price_does_not_inflate_market():
    report = run(rec(stage="cancelled"))
    assert report["counts"]["relevant_lots_awards"] == 1
    assert report["observed_award_values_rub"]["confirmed_addressable_total"] == "0"
    assert report["observed_award_values_rub"]["relevant_full_procurement_envelope"] == "0"


def test_price_disagreement_same_snapshot_quarantined():
    conflict = rec(value_rub="290000000", source="synthetic_etp", external_id="diff")
    result = run(rec(), conflict)
    item = result["procurements"][0]
    assert "CONFLICT_VALUE_RUB" in item["quality_flags"]
    assert item["value_rub"] is None
    assert result["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "0"


def test_unproved_winner_and_participants_never_inferred():
    first = rec(participants=[{"inn": "7801010101", "name": "Unverified bidder"}])
    first["evidence"][0]["facts"].remove("winner")
    result = run(first)
    item = result["procurements"][0]
    assert item["winner"] is None
    assert item["participants"] == []
    assert all(a["role"] != "epc_contractor" for a in result["accounts"])


def test_missing_scope_proof_does_not_impute_epc():
    first = rec()
    first["evidence"][0]["facts"].remove("scope")
    result = run(first)
    assert result["procurements"][0]["scope"] == "unknown"
    assert result["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "0"


def test_no_product_citation_means_not_relevant():
    first = rec()
    first["evidence"][0]["facts"].remove("product:statcom")
    result = run(first)
    assert result["counts"]["deduplicated_lots_awards"] == 1
    assert result["counts"]["relevant_lots_awards"] == 0


def test_alias_is_not_self_evidencing():
    first = rec()
    first["evidence"][0]["excerpt"] = "statcom"
    first["evidence"][0]["facts"].remove("product:statcom")
    assert run(first)["counts"]["relevant_lots_awards"] == 0


def test_period_is_closed_and_events_outside_excluded():
    result = run(rec(event_on="2023-10-23"), rec(procurement_id="P-300",
                                                   award_id="C-300", event_on="2023-10-24"))
    assert result["counts"]["in_window_records"] == 1
    assert result["procurements"][0]["procurement_id"] == "P-300"


def test_as_of_future_observation_rejected():
    with pytest.raises(MarketInputError, match="newer"):
        run(rec(observed_on="2026-10-25"))


@pytest.mark.parametrize("money", ["-1", "NaN", "Infinity", "bad", 1.5, True])
def test_invalid_or_unsafe_money_input_fails_closed(money):
    with pytest.raises(MarketInputError):
        run(rec(value_rub=money))


def test_unknown_product_id_in_evidence_rejected():
    first = rec()
    first["evidence"][0]["facts"] = ["product:another-product"]
    with pytest.raises(MarketInputError, match="unknown products"):
        run(first)


def test_invalid_supplier_or_window_rejected():
    p = portfolio()
    p["window_from"] = "2026-12-01"
    with pytest.raises(MarketInputError):
        analyze_market(p)
    p = portfolio()
    p["supplier"]["products"].append(deepcopy(p["supplier"]["products"][0]))
    with pytest.raises(MarketInputError, match="unique"):
        analyze_market(p)


def test_later_nonmatching_revision_does_not_silently_restore_old_product():
    old = rec(observed_on="2026-08-01")
    new = rec(observed_on="2026-10-23", external_id="rev2",
              evidence=[{**rec()["evidence"][0],
                         "url": "https://example.org/synthetic/rev2",
                         "facts": ["buyer", "scope", "value"]}])
    report = run(old, new)
    # An older technical spec is not sufficient to prove latest-demand relevance.
    assert report["counts"]["relevant_lots_awards"] == 0


def test_work_package_identity_and_price_are_not_buyer_fuzzy_merged():
    a = rec(procurement_id="X", award_id="A")
    b = rec(procurement_id="X", award_id="B")
    assert run(a, b)["counts"]["deduplicated_lots_awards"] == 2


def test_stale_or_unproven_open_deadline_not_live():
    first = rec(stage="open", award_id=None, observed_on="2026-09-01")
    assert run(first)["counts"]["open_opportunities"] == 0
    second = rec(stage="open", award_id=None)
    second["evidence"][0]["facts"].remove("deadline")
    assert run(second)["counts"]["open_opportunities"] == 0
    assert "OPEN_STATUS_UNVERIFIED_OR_STALE" in run(second)["procurements"][0]["quality_flags"]


def test_award_nmck_ceiling_not_contract_price():
    item = rec(price_basis="ceiling")
    facts = item["evidence"][0]["facts"]
    facts.remove("price_basis:contract")
    facts.append("price_basis:ceiling")
    report = run(item)
    assert report["procurements"][0]["nmck_rub"] == "300000000"
    assert report["observed_award_values_rub"]["relevant_full_procurement_envelope"] == "0"


def test_unverified_price_basis_not_counted():
    item = rec()
    item["evidence"][0]["facts"].remove("price_basis:contract")
    assert run(item)["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "0"


def test_component_over_contract_quarantined():
    item = rec(component_value_rub="900000000")
    item["evidence"][0]["facts"].extend(["component_value", "component_basis:contract_line"])
    report = run(item)
    assert "COMPONENT_EXCEEDS_AWARD_PRICE" in report["procurements"][0]["quality_flags"]
    assert report["observed_award_values_rub"]["confirmed_addressable_total"] == "0"


def test_design_award_does_not_count_bill_of_materials_as_equipment_purchase():
    item = rec(scope="design", component_value_rub="10000000")
    item["evidence"][0]["facts"].extend(["component_value", "component_basis:contract_line"])
    assert run(item)["observed_award_values_rub"]["confirmed_addressable_total"] == "0"


def test_yearly_observations_and_verified_participants():
    one = rec(participants=[{"inn": "7801010101", "name": "SYNTHETIC Bidder"}])
    one["evidence"][0]["facts"].append("participants")
    other = rec(procurement_id="OTHER", award_id="OTHER", event_on="2024-01-02")
    report = run(one, other)
    assert report["annual_observations"]["2024"]["procedures"] == 1
    assert report["annual_observations"]["2025"]["procedures"] == 1
    assert report["observed_participants"][0]["count"] == 1
    assert report["procedures_without_verified_participant_roster"] == 1


def test_same_inn_buyer_alias_is_not_identity_conflict():
    mirrored = rec(source="synthetic_etp", external_id="mirror")
    mirrored["buyer"] = {"inn": "7707083893", "name": "Другое написание"}
    report = run(rec(), mirrored)
    assert "CONFLICT_BUYER" not in report["procurements"][0]["quality_flags"]
    assert report["procurements"][0]["buyer"]["inn"] == "7707083893"


def test_verified_participant_rosters_merge_across_mirrors():
    a = rec(participants=[{"inn": "7801010101", "name": "Участник A"}])
    a["evidence"][0]["facts"].append("participants")
    b = rec(source="synthetic_etp", external_id="mirror",
            participants=[{"inn": "7701020102", "name": "Участник B"}])
    b["evidence"][0]["facts"].append("participants")
    report = run(a, b)
    assert len(report["procurements"][0]["participants"]) == 2
    assert len(report["observed_participants"]) == 2
