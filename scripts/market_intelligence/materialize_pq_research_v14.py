"""Append three source-backed PQ leads to v13 without modifying 71 imported records.

Research-only; production Data Platform v12 remains at 71 until separate consent.
"""
from __future__ import annotations
import json
from pathlib import Path
from materialize_pq_research_v13 import materialize as v13

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v14.manifest.json"

def materialize():
    m=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    d=json.loads((DATA/m["delta"]).read_text(encoding="utf-8"))
    base=v13()
    rows=list(base["records"])
    if len(rows)!=m["base_lot_level_rows"] or len(d["records"])!=m["delta_lot_level_rows"]:
        raise ValueError("PQ v14 base/delta size drift")
    seen={r["canonical_id"] for r in rows}
    if len(seen)!=len(rows):
        raise ValueError("duplicate existing PQ source ID")
    for raw in d["records"]:
        if raw["id"] in seen:
            raise ValueError("duplicated new PQ source")
        if not m["rolling_window"]["from"]<=raw["published"]<=m["rolling_window"]["to"]:
            raise ValueError("source outside rolling 3-year period")
        if not raw["source"].startswith("https://"):
            raise ValueError("missing source")
        if raw.get("contract_rub") is not None and not raw.get("contract_source_grade","").startswith("secondary_"):
            raise ValueError("new contract must remain secondhand")
        item={
            "id":"pq-v14-"+raw["notice"],
            "canonical_id":raw["id"],
            "procedure_id":raw["notice"],
            "publication_date":raw["published"],
            "date_basis":"secondary_public_procurement_card",
            "procurement_regime":raw["regime"],
            "platform":raw["platform"],
            "customer":{"name":raw["buyer"],"inn":raw["inn"]},
            "project":raw["title"],
            "description":raw["subject"],
            "family":raw["category"],
            "scope":raw["scope"],
            "nmck_rub":raw["nmc_rub"],
            "reported_price_kind":"initial_price_including_vat_reported_secondary" if raw.get("nmc_rub") is not None else None,
            "reported_contract_total_rub":raw["contract_rub"],
            "reported_contract_total_source_tier":raw.get("contract_source_grade"),
            "reported_contract_date":raw.get("contract_date"),
            "equipment_voltage_kv":raw["voltage_kv"],
            "market_scope":"voltage_class_not_confirmed_for_pq_device",
            "quantity":None,
            "quantity_unit":None,
            "deadline_date":raw["deadline"],
            "demand_group":raw["project"],
            "status":"public_aggregator_notice_original_protocol_pending",
            "evidence":[{"url":raw["source"],"source_tier":raw["grade"],"locator":raw["title"],"excerpt":raw["subject"]}],
            "supplier_verified":False,
            "supplier_inn":None,
            "pq_equipment_only_contract_rub":None,
            "notes":raw["notes"],
        }
        seen.add(raw["id"])
        rows.append(item)
    if len(rows)!=m["total_lot_level_rows"] or len(seen)!=len(rows):
        raise ValueError("inconsistent v14 total or identifiers")
    return {
        **base,
        "records":rows,
        "data_version":"v14",
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "prior_lot_level_records":79,
            "added_lot_level_records":3,
            "total_lot_level_records":len(rows),
            "primary_signed_contracts_added":0,
            "production_structured_records_imported":71,
            "new_records_pending_import":11,
        },
        "seed_completeness":"Discovered examples, not all tenders in the Russian procurement universe.",
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
