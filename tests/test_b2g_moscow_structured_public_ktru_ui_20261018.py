"""Public catalog affordance verified, but no open selectable public code 62."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = json.loads(
    (ROOT / "docs/roadmap/b2g_moscow_public_structured_ktru_ui_2026-10-18.json")
    .read_text("utf-8")
)


def test_source_rendered_real_two_classification_controls_but_no_code_selected():
    r = RECEIPT
    assert r["schema_version"] == "ta-b2g-moscow-public-structured-ktru-ui-v1"
    assert r["official_first_party_source"] == "https://zakupki.mos.ru/"
    assert r["real_ui_registry_navigated"] is True
    assert r["real_ui_basic_filters_opened"] is True
    assert r["real_ui_extended_filters_opened"] is True
    assert [e["label"] for e in r["source_exact_field_observations"]] == [
        "КТРУ", "Вид продукции"
    ]
    for e in r["source_exact_field_observations"]:
        assert e["sourceBefore"]["has_exact_public_label"] is True
        assert e["sourceBefore"]["has_real_dropdown"] is True
        assert e["sourceBefore"]["role"] == "listbox"
        assert e["clicked"] is True
        assert e["after"]["aria_expanded"] == "false"
        assert e["after"]["visible_options"] == []
        assert e["after"]["dropdown_has_search_input"] is False
        assert e["observed_at_utc"]
    assert r["availability_of_classification_choices_verified"] is False
    assert r["class_62_code_selected"] is False
    assert r["submitted_structured_ktru_query"] is False


def test_empty_selectors_are_an_access_gap_not_evidence_no_it_market():
    r = RECEIPT
    assert r["lack_of_options_does_not_prove_no_live_IT_auctions"] is True
    assert r["company_authenticated"] is False
    assert r["company_bids_submitted"] == 0
    assert r["owner_go"] is False
    assert r["verified_corporate_b2b_leads"] == 0
    assert r["disposable_browser_profile_saved"] is False


def test_reproducible_public_dom_inspection_has_no_company_actions():
    script = (
        ROOT / "scripts/acceptance/audit_moscow_public_structured_ktru_20261018.mjs"
    ).read_text("utf8")
    assert "Реестр котировочных сессий" in script
    assert "Показать фильтры" in script
    assert "Показать расширенные фильтры" in script
    assert "['КТРУ','Вид продукции']" in script
    assert "sourceBefore.has_exact_public_label" in script
    assert "await rm(profile" in script
    assert "--user-data-dir=" in script
    assert "submitted_structured_ktru_query:false" in script
    assert "company_bids_submitted:0" in script
    for disallowed in ("submitBid(", "registerCompany(", "newapi/api/", "/api/auction/search"):
        assert disallowed not in script
