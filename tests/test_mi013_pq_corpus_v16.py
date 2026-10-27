"""v16 87-source no-invented equipment-sales regression."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]/"scripts/market_intelligence"

def load(ver):
    p=subprocess.run([sys.executable,str(HERE/f"materialize_pq_research_v{ver}.py")],
        capture_output=True,text=True,check=True,timeout=35)
    return json.loads(p.stdout)["records"]

def test_append_preserves_prior_84_and_87_unique():
    prior,now=load(15),load(16)
    assert len(prior)==84
    assert len(now)==87
    assert now[:84]==prior
    assert len({r["canonical_id"] for r in now})==87

def test_hani_lopcha_one_project_distinct_2024_epc_lots():
    rows=load(16)[84:]
    a,b=rows[:2]
    assert a["demand_group"]==b["demand_group"]
    assert a["nmck_rub"]=="1571458880.00"
    assert b["nmck_rub"]=="1518147770.00"
    assert a["procedure_id"] is None
    assert a["source_identifier_masked"] is True
    assert b["procedure_id"]=="32413581034"
    assert all(r["equipment_voltage_kv"] is None for r in (a,b))
    assert a["reported_contract_total_source_tier"]=="secondary_aggregator"
    assert not a["supplier_verified"]

def test_vanino_is_design_not_sk_rm_sale():
    r=load(16)[-1]
    assert r["procedure_id"]=="32616506708"
    assert r["nmck_rub"]=="13523603.17"
    assert r["scope"]=="design"
    assert r["reported_contract_total_rub"] is None
    assert r["equipment_voltage_kv"] is None
    assert r["supplier_verified"] is False
