"""MI-013 v12: original SHA-verified source corrects voltage and cost, not sales."""
from __future__ import annotations
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/market_intelligence"
DATA=ROOT/"data/market_intelligence/power_quality"

def load(version):
    proc=subprocess.run([sys.executable,str(SCRIPTS/f"materialize_pq_research_v{version}.py")],
        text=True,capture_output=True,check=True,timeout=35)
    return json.loads(proc.stdout)

def test_v12_keeps_original_71_ids_order_and_patches_only_three():
    old=load(11)["records"]
    new=load(12)["records"]
    assert len(old)==len(new)==71
    assert [r["canonical_id"] for r in old]==[r["canonical_id"] for r in new]
    changes=[(a["canonical_id"],b["canonical_id"]) for a,b in zip(old,new) if a!=b]
    assert {x[0] for x in changes}=={
        "223fz:32616435269:lot1","223fz:32515044454:lot1","223fz:32616354211:lot1"
    }
    assert len(changes)==3

def test_v12_medium_voltage_net_price_reconciles_original_gross_22pct():
    record=next(x for x in load(12)["records"] if x["procedure_id"]=="32616435269")
    assert record["source_original_docs_verified"] is True
    assert record["family"]=="hybrid_reactive_power_source"
    assert record["equipment_voltage_kv"] is None
    assert record["equipment_voltage_kv_set"]==[10,110]
    assert record["nominal_converter_voltage_kv"]==10
    assert record["complete_system_voltage_kv"]==110
    assert record["nominal_reactive_power_inductive_mvar"]==30
    assert record["nominal_reactive_power_capacitive_mvar"]==52
    assert record["nmc_vat_rate_pct"]==22
    net=Decimal(record["nmc_net_rub"])
    entries=[record["boq_mpu_10kv_net_rub"],record["boq_bsk_110kv_net_rub"],record["boq_supervision_net_rub"]]
    assert net==sum((Decimal(x) for x in entries),Decimal(0))==Decimal("370504918.04")
    assert (net*Decimal("1.22")).quantize(Decimal("0.01"))==Decimal("452016000.01")
    assert record["nmck_rub"]==record["nmc_gross_rub"]=="452016000.01"
    assert record["boq_mpu_10kv_net_rub"]=="335351974.38"
    assert record["supplier_verified"] is False
    assert record["reported_contract_total_rub"] is None
    assert record["pq_equipment_only_contract_rub"] is None

def test_original_document_sha256_provenance_and_metadata():
    src=json.loads((DATA/"verified_32616435269_original_archive_20261027.json").read_text(encoding="utf-8"))
    assert src["original_archive_sha256"]=="5f9e406c56254891514dec2e9f8689417782bce298e5e4cb433375d1806cbb65"
    assert src["original_archive_bytes"]==695885
    assert src["archive_extracted_verified"] is True
    assert src["summary"]["contract_price_rub"] is None
    assert src["summary"]["contract_supplier_verified"] is False
    assert src["equipment_components"][0]["nominal_voltage_kv"]==10
    assert src["equipment_components"][1]["nominal_voltage_kv"]==110
    assert len(src["documents"])>=4

def test_design_and_supply_notice_share_one_project_not_one_contract():
    records=load(12)["records"]
    matching=[r for r in records if r.get("project_demand_group")=="TYAZHINSKAYA-SKRM52-2025-2026"]
    assert len(matching)==3
    assert {r["procedure_id"] for r in matching}=={"32515044454","32616354211","32616435269"}
    assert sum(r["scope"]=="design" for r in matching)==2
    assert sum(r["scope"]=="supply" for r in matching)==1
    assert sum(r.get("supplier_verified") is True for r in matching)==0


def test_design_contract_date_remains_secondary_and_awardee_unverified():
    r=next(r for r in load(12)["records"] if r["canonical_id"]=="223fz:32616354211:lot1")
    assert r["reported_contract_date"]=="2026-09-23"
    assert r["reported_contract_date_source_tier"].startswith("third_party")
    assert r["reported_contract_total_rub"]=="7406851.40"
    assert r["supplier_verified"] is False
    assert not (r.get("registry_contract") or {}).get("signed_contract_registry_verified")
    assert any("tendem.ru" in e["url"] for e in r["evidence"])
