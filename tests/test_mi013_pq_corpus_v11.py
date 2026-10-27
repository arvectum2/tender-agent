"""MI-013 v11: two new notices are three lot-level records, not three tenders."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/market_intelligence"
DATA = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"


def read_materialized(version):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"materialize_pq_research_v{version}.py")],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(p.stdout)


def test_v11_preserves_all_68_prior_records_and_three_unique_lots():
    old, new = read_materialized(10), read_materialized(11)
    assert len(old["records"]) == 68
    assert new["records"][:68] == old["records"]
    assert len(new["records"]) == 71
    assert len({r["canonical_id"] for r in new["records"]}) == 71
    assert len({r["procedure_id"] for r in new["records"][68:]}) == 2


def test_besk_two_lots_are_not_two_independent_notices_or_awards():
    extra = read_materialized(11)["records"][68:]
    kep = [r for r in extra if r["procedure_id"] == "32616474682"]
    assert len(kep) == 2
    assert {r["lot_number"] for r in kep} == {1, 2}
    assert {r["quantity"] for r in kep} == {11, 16}
    assert {r["customer"]["inn"] for r in kep} == {"0273056757", "0277071467"}
    assert sum(int(round(float(r["nmck_rub"]) * 100)) for r in kep) == 245265041
    assert all(r["joint_notice_nmck_ex_vat_rub"] == "2452650.41" for r in kep)
    assert all(r["reported_price_kind"] == "initial_price_excluding_vat" for r in kep)
    assert all(r["equipment_voltage_kv"] is None for r in kep)
    assert all(r["supplier_verified"] is False for r in kep)
    assert all(r["reported_contract_total_rub"] is None for r in kep)
    assert all(any(e["source_tier"] == "primary_platform" for e in r["evidence"]) for r in kep)


def test_rosseti_high_initial_price_and_october_amendment_not_contract():
    extra = read_materialized(11)["records"][68:]
    r = next(x for x in extra if x["procedure_id"] == "32616435269")
    assert r["nmck_rub"] == "452016000.01"
    assert r["nmck_original_rub"] == "452016000.00"
    assert r["bid_deadline_current"] == "2026-10-30T12:00:00"
    assert r["equipment_voltage_kv"] is None
    assert r["quantity"] is None
    assert r["reported_contract_total_rub"] is None
    assert r["supplier_verified"] is False
    assert r["market_scope"] == "voltage_unverified_not_strict_6_35kv"


def test_lot_conflicting_secondary_sources_not_silently_reconciled():
    d = json.loads((DATA / "besk_joint_kep_rosseti_high_value_2026_delta.json").read_text())
    second = next(r for r in d["records"] if r["lot_number"] == 2 and r["procedure_id"] == "32616474682")
    assert second["nmck_rub"] == "1471296.08"
    assert any(e["source_tier"] == "third_party_conflict" for e in second["evidence"])
    assert "1 471 296,16" in second["notes"]
