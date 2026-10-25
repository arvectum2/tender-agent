"""Bounded Power Quality source recall and procurement coverage regression checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.modules.market_intelligence.mi003_pq_evaluation import (
    evaluate,
    render_markdown,
)
from src.modules.market_intelligence.power_quality_pilot import PilotEvidenceError

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/market_intelligence/power_quality"


@pytest.fixture
def inputs():
    data = json.loads((INPUT / "verified_public_leads.v1.json").read_text())
    ontology = yaml.safe_load((INPUT / "ontology.v1.yaml").read_text())
    return data, ontology


def test_actual_curated_titles_not_hidden_annexes_only(inputs):
    report = evaluate(*inputs)
    assert report["labelled_lead_count"] == 12
    assert report["expected_family_found_count"] == 12
    assert report["sample_description_label_recall"] == 1.0
    assert report["sample_type"] == "purposefully_discovered_public_leads_not_population"
    assert all(x["expected_label_found_in_description"] for x in report["per_lead"])
    assert {x["source_tier"] for x in report["per_lead"]} == {
        "primary_platform", "third_party_only"
    }


def test_synthetic_hard_negatives_are_clearly_labelled(inputs):
    report = evaluate(*inputs)
    assert report["negative_controls_are_synthetic"] is True
    assert report["negative_controls_count"] == 8
    assert report["negative_control_false_positives"] == 0


def test_market_size_and_winners_are_unknown_not_zero(inputs):
    report = evaluate(*inputs)
    assert report["verified_hardware_market_size_rub"] is None
    assert report["known_winning_epc"] == []
    assert report["known_verified_designers"] == []
    assert report["project_role_graph"]["verified_edges"] == []
    assert report["unpriced_relevant_procedures"] == 12
    assert all(not b["role_verified_from_official_protocol"]
               for b in report["reported_buyers_unverified"])


def test_playbook_is_actionable_without_assuming_winners_or_open_tenders(inputs):
    report = evaluate(*inputs)
    rows = report["account_playbook_unreviewed"]
    assert len(rows) == 10
    lukoil = next(r for r in rows if "ЛУКОЙЛ-Западная Сибирь" in r["buyer_name_reported"])
    assert lukoil["observed_procedures"] == 2
    assert lukoil["initial_priority_hypothesis"] == "P1"
    assert len(lukoil["source_urls"]) == 3  # two cards + one protocol link
    assert "ukrm" in lukoil["product_families"]
    for item in rows:
        assert item["proposed_actions"]
        assert all(x.startswith("https://") for x in item["source_urls"])
        assert item["recommended_state"] == "manual_qualification_not_automated_outreach"
        assert not item["verified_current_open_opportunity"]
        assert item["verified_winning_supplier"] is None
        assert not item["legal_role_of_epc_verified"]


def test_37_calendar_months_times_seven_source_categories(inputs):
    report = evaluate(*inputs)
    cov = report["coverage"]
    assert cov["source_month_slots"] == 259
    assert cov["verified_complete_slots"] == 0
    assert cov["full_market_census"] is False
    assert cov["national_tam_rub"] is None
    broken = [x for x in cov["coverage_grid"] if x["month"] == "2026-10"
              and x["source"] in {"EIS-44FZ", "EIS-223FZ"}]
    assert len(broken) == 2 and all(x["status"] == "failed" for x in broken)
    assert all(x["expected"] is None for x in cov["coverage_grid"])


def test_dropped_primary_urls_fails_closed(inputs):
    seed, onto = inputs
    seed["records"][0]["evidence"] = []
    with pytest.raises(PilotEvidenceError, match="evidence required"):
        evaluate(seed, onto)


def test_markdown_discloses_every_method_limit(inputs):
    report = evaluate(*inputs)
    md = render_markdown(report)
    assert "12" in md
    assert "Does NOT measure embedded EPC" in md
    assert "NOT AVAILABLE" in md
    assert "PPTX" in md
