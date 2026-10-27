"""MI-013 v12 staging remains 71 stable resources, with audited original 10/110kV BOM."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/market_intelligence"

def load_stage(filename):
    out=subprocess.run([sys.executable,str(SCRIPTS/filename)],capture_output=True,text=True,check=True,timeout=35)
    return [json.loads(s) for s in out.stdout.splitlines() if s.strip()]

def test_v12_preserves_71_v11_stable_keys_and_updates_hash_for_corrected_item():
    old=load_stage("export_pq_data_platform_v11.py")
    new=load_stage("export_pq_data_platform_v12.py")
    assert len(old)==len(new)==71
    assert [a["resource_id"] for a in old]==[a["resource_id"] for a in new]
    assert all(r["metadata"]["data_version"]=="v12" for r in new)
    assert len({r["external_id"] for r in new})==71
    for r in new:
        rid=hashlib.sha256(r["external_id"].encode("utf-8")).hexdigest()
        assert r["resource_id"]==rid[:48]
        assert r["canonical_uri"]=="urn:arvectum:pq:procurement:"+rid

def test_v12_source_provenance_and_price_fields_unmix_equipment_and_contract():
    new=load_stage("export_pq_data_platform_v12.py")
    item=next(x for x in new if x["external_id"]=="223fz:32616435269:lot1")
    assert item["metadata"]["reported_price_kind"]=="initial_price_including_vat22_original_notice_verified"
    assert item["metadata"]["nmck_rub"]=="452016000.01"
    assert item["metadata"]["winning_supplier_only_if_verified"] is None
    assert item["metadata"]["original_primary_registry_verified"] is False
    rec=item["source_record"]
    assert rec["source_original_docs_verified"] is True
    assert rec["project_demand_group"]=="TYAZHINSKAYA-SKRM52-2025-2026"
    assert rec["equipment_voltage_kv_set"]==[10,110]
    assert rec["boq_mpu_10kv_net_rub"]=="335351974.38"
    assert rec["boq_bsk_110kv_net_rub"]=="33723435.46"
    assert rec["pq_equipment_only_contract_rub"] is None
    assert any(e["source_tier"]=="primary_original_document_rehosted_sha256_verified" for e in rec["evidence"])

def test_v12_quality_snapshot_enrichment_keeps_original_evidence_types_distinct():
    data=ROOT/"data/market_intelligence/power_quality"
    s=json.loads((data/"evidence_quality_snapshot_20261027.v12.json").read_text())
    assert s["procurement_records"]==71
    assert s["records_with_primary_platform_evidence_count"]==13
    assert s["registered_contract_primary_verified_count"]==4
    assert s["original_procurement_documents_mirrored_and_sha256_verified_count"]==1
    assert s["family_counts"]["hybrid_reactive_power_source"]==1
    assert sum(s["family_counts"].values())==71
