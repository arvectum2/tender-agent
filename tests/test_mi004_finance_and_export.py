"""MI-004 evidence-aware procurement finance and safe report export contract."""

from __future__ import annotations

import csv
import html
import io
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.modules.market_intelligence.finance_and_export import (
    FinanceEvidenceError,
    audit_project_finance,
    export_account_csv,
    export_customer_html,
)


def _fact(
    amount: str, *,
    project: str = "project-001",
    contract: str = "C-001",
    notice: str = "32600001111",
    tier: str = "end_buyer",
    scope: str = "epc",
    kind: str = "contract_total",
    line: str = "",
    family: str = "",
    status: str = "awarded",
    dedicated: bool = False,
    revised: str = "2026-10-20",
    source: str = "https://zakupki.gov.ru/registry/contract/C-001",
):
    return {
        "project_id": project,
        "contract_id": contract, "notice_id": notice, "lot_id": "1",
        "tier": tier, "scope": scope, "price_type": kind, "status": status,
        "line_id": line, "equipment_family": family,
        "dedicated_equipment_lot": dedicated,
        "revision_on": revised, "as_of": revised,
        "amount_rub": amount,
        "evidence": {
            "source_type": "signed_contract",
            "review_state": "approved",
            "reviewer": "analyst_01",
            "url": source,
            "locator": "Договор, спецификация, строка 3",
            "excerpt": "Компенсатор реактивной мощности и работы по договору",
            "sha256": "a" * 64,
        },
    }


def test_project_scope_separates_hardware_from_epc_and_subcontract():
    facts = [
        _fact("300000000"),
        _fact("25000000", kind="equipment_line", line="EQ-STATCOM-1", family="statcom"),
        _fact("18000000", tier="subcontract", contract="SUB-1", notice="private-1",
              scope="supply", kind="contract_total", dedicated=True, family="statcom"),
        _fact("2000000", contract="DESIGN-1", notice="32600002222", scope="design"),
        _fact("500000", contract="SERVICE-1", notice="32600003333", scope="maintenance"),
        _fact("350000000", contract="EPC-CEILING", notice="32600004444", kind="ceiling",
              status="open"),
    ]
    result = audit_project_finance(facts, as_of="2026-10-24")
    project = result["project_finance"][0]
    assert project["contracted_equipment_rub"] == "25000000"
    assert project["full_epc_contract_envelope_rub"] == "300000000"
    assert project["subcontract_chain_value_rub_not_additive"] == "18000000"
    assert project["design_contract_rub"] == "2000000"
    assert project["service_contract_rub"] == "500000"
    assert project["published_ceiling_rub_not_awarded"] == "350000000"
    assert result["observed_confirmed_contracted_equipment_rub"] == "25000000"
    assert result["national_tam_rub"] is None
    assert result["national_sam_rub"] is None
    assert result["national_som_rub"] is None
    assert result["money_definition"] == "contracted, not payment/executed revenue"


def test_dedicated_supply_counts_only_when_source_proves_dedicated_lot():
    facts = [
        _fact("9900000", contract="SUPPLY-1", notice="32600008881",
              scope="supply", dedicated=True, family="ukrm"),
        _fact("6000000", contract="MIXED-1", notice="32600008882",
              scope="supply", dedicated=False, family="ukrm"),
    ]
    result = audit_project_finance(facts, as_of="2026-10-24")
    assert result["observed_confirmed_contracted_equipment_rub"] == "9900000"


def test_same_award_in_two_mirrors_does_not_double_count():
    x = _fact("12000000", scope="supply", family="statcom", dedicated=True)
    y = deepcopy(x)
    y["evidence"]["url"] = "https://zakupki.gov.ru/mirror/contract"
    report = audit_project_finance([x, y], as_of="2026-10-24")
    assert report["source_duplicates_removed"] == 1
    assert report["observed_confirmed_contracted_equipment_rub"] == "12000000"


def test_latest_price_revision_replaces_old_without_addition():
    prior = _fact("14000000", scope="supply", family="statcom", dedicated=True,
                  revised="2026-10-18")
    latest = _fact("17000000", scope="supply", family="statcom", dedicated=True,
                   revised="2026-10-23")
    report = audit_project_finance([prior, latest], as_of="2026-10-24")
    assert report["observed_confirmed_contracted_equipment_rub"] == "17000000"
    assert not report["quarantined_price_facts"]


def test_same_revision_conflict_goes_to_quarantine():
    prior = _fact("17000000", scope="supply", family="statcom", dedicated=True)
    altered = _fact("22000000", scope="supply", family="statcom", dedicated=True)
    report = audit_project_finance([prior, altered], as_of="2026-10-24")
    assert report["observed_confirmed_contracted_equipment_rub"] is None
    assert report["quarantined_price_facts"][0]["reason"] == (
        "conflicting_same_revision_primary_sources"
    )


def test_overpriced_line_quarantined_and_not_promoted_as_dedicated_total():
    total = _fact("9000000", scope="supply", family="statcom", dedicated=True)
    line = _fact("13000000", scope="supply", family="statcom", kind="equipment_line", line="EQ1")
    report = audit_project_finance([total, line], as_of="2026-10-24")
    assert report["observed_confirmed_contracted_equipment_rub"] is None
    assert report["quarantined_price_facts"][0]["reason"] == "equipment_lines_exceed_contract_total"


def test_same_project_family_multiple_contracts_conservative_de_dup():
    a = _fact("25000000", contract="EPC-1", notice="32600000001",
              kind="equipment_line", line="EQ1", scope="epc", family="statcom")
    b = _fact("22000000", contract="SUP-2", notice="32600000002",
              kind="contract_total", scope="supply", family="statcom", dedicated=True)
    report = audit_project_finance([a, b], as_of="2026-10-24")
    assert report["observed_confirmed_contracted_equipment_rub"] == "25000000"
    assert report["project_finance"][0]["conservative_project_family_dedup"] is True
    assert report["cross_contract_lifecycle_review"]
    assert report["cross_contract_lifecycle_review"][0]["conservative_max_contract_applied"]


def test_same_project_different_families_remain_distinct():
    a = _fact("12000000", contract="SUP-1", notice="32600000001",
              scope="supply", family="ukrm", dedicated=True)
    b = _fact("7000000", contract="SUP-2", notice="32600000002",
              scope="supply", family="harmonic_filter", dedicated=True)
    report = audit_project_finance([a, b], as_of="2026-10-24")
    assert report["observed_confirmed_contracted_equipment_rub"] == "19000000"
    assert not report["cross_contract_lifecycle_review"]


@pytest.mark.parametrize(
    "change",
    [
        {"amount_rub": "-1"},
        {"amount_rub": "NaN"},
        {"amount_rub": "1e999999"},
        {"evidence": {"source_type": "third_party"}},
        {"status": "unrecognized"},
        {"tier": "unknown"},
        {"revision_on": "2027-01-01"},
    ],
)
def test_invalid_or_unproven_claims_rejected(change):
    base = _fact("100")
    base.update(change)
    with pytest.raises(FinanceEvidenceError):
        audit_project_finance([base], as_of="2026-10-24")


def test_award_protocol_alone_cannot_be_used_as_signed_contract_value():
    row = _fact("1000000", scope="supply", family="ukrm", dedicated=True)
    row["evidence"]["source_type"] = "official_protocol"
    with pytest.raises(FinanceEvidenceError, match="contract/registry proof"):
        audit_project_finance([row], as_of="2026-10-24")


def test_zero_confirmed_spend_not_fake_zero_market():
    report = audit_project_finance([], as_of="2026-10-24", source_coverage_certified=False)
    assert report["observed_confirmed_contracted_equipment_rub"] is None
    assert report["national_tam_rub"] is None
    assert report["project_finance"] == []


def test_export_customer_report_is_source_bound_and_not_live_opportunities():
    report = json.loads(Path(
        "data/market_intelligence/power_quality/mi003_evaluation.v1.json"
    ).read_text(encoding="utf-8"))
    rendered = export_customer_html(report)
    assert "<!doctype html>" in rendered
    assert "ЛУКОЙЛ" in rendered
    assert "Суходол" in rendered
    assert "не весь рынок РФ" in rendered
    assert 'rel="noreferrer noopener"' in rendered
    assert "закупки не подтверждены" in rendered
    assert "default-src 'none'" in rendered
    assert rendered.count("<tr>") >= 10


def test_html_escapes_company_name_and_filters_non_https_urls():
    report = {
        "window": ["2023-10-24", "2026-10-24"],
        "labelled_lead_count": 1, "coverage": {},
        "critical_caveats": ["<script>alert('bad')</script>"],
        "account_playbook_unreviewed": [{
            "buyer_name_reported": '<img src=x onerror=alert(1)>',
            "initial_priority_hypothesis": "=cmd('bad')",
            "observed_procedures": 1, "product_families": ["ukrm"],
            "source_urls": ["javascript:alert(1)", "https://example.org/?q=x&lang=ru"],
            "proposed_actions": ["<script>evil()</script>"],
        }],
    }
    rendered = export_customer_html(report)
    assert "<script>" not in rendered
    assert "<img " not in rendered
    assert "javascript:" not in rendered
    assert html.escape('<img src=x onerror=alert(1)>') in rendered
    assert 'href="https://example.org/?q=x&amp;lang=ru"' in rendered


def test_csv_defends_formula_injection_and_preserves_utf8_bom():
    report = {"account_playbook_unreviewed": [
        {
            "buyer_name_reported": " =HYPERLINK(\"https://bad\")",
            "initial_priority_hypothesis": "+SUM(1,2)",
            "observed_procedures": 3, "work_packages": ["supply"],
            "proposed_actions": ["@evil()"], "source_urls": ["https://example.org"],
        }
    ]}
    csv_text = export_account_csv(report)
    assert csv_text.startswith("\ufeff")
    records = list(csv.reader(io.StringIO(csv_text.removeprefix("\ufeff"))))
    assert records[1][0].startswith("'")
    assert records[1][1].startswith("'")
    assert records[1][4].startswith("'")
    assert records[1][2] == "3"
