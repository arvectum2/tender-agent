"""MI-013 v16 research extension (87 lot-level sources), no production writes."""
from __future__ import annotations
import json
from pathlib import Path
from materialize_pq_research_v15 import materialize as previous

ROOT=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v16.manifest.json"

def materialize():
    m=json.loads((ROOT/MANIFEST).read_text(encoding="utf-8"))
    d=json.loads((ROOT/m["delta_file"]).read_text(encoding="utf-8"))
    old=previous()
    items=list(old["records"])
    if len(items)!=m["base_rows"] or len(d["records"])!=m["delta_rows"]:
        raise ValueError("source count mismatch")
    keys={x["canonical_id"] for x in items}
    if len(keys)!=len(items):
        raise ValueError("duplicate existing IDs")
    for x in d["records"]:
        if x["canonical_id"] in keys:
            raise ValueError("duplicate source ID")
        if not (m["period"]["from"]<=x["publication_date"]<=m["period"]["to"]):
            raise ValueError("publication outside rolling period")
        if not x["evidence"] or any(not y["url"].startswith("https://") for y in x["evidence"]):
            raise ValueError("missing original source locator")
        if x["scope"]=="mixed_epc" and x["voltage_kv"] is not None:
            raise ValueError("220kV substation doesn't establish device voltage")
        row={
            "id":"pq-v16-"+(x["procedure_id"] or x["canonical_id"]),
            "canonical_id":x["canonical_id"],
            "procedure_id":x["procedure_id"],
            "publication_date":x["publication_date"],
            "date_basis":"secondary_procurement_source",
            "procurement_regime":"223-fz",
            "customer":{"name":x["customer"],"inn":x["buyer_inn"]},
            "project":x["title"],
            "description":x["title"],
            "family":x["family"],
            "scope":x["scope"],
            "equipment_voltage_kv":x["voltage_kv"],
            "market_scope":"medium_voltage_equipment_not_confirmed_in_mixed_EPC_or_design",
            "nmck_rub":x["nmc_rub"],
            "reported_price_kind":"initial_price_whole_procurement",
            "reported_contract_total_rub":x.get("secondary_contract_rub"),
            "reported_contract_total_source_tier":"secondary_aggregator" if x.get("secondary_contract_rub") else None,
            "reported_contract_date":x.get("secondary_contract_date"),
            "contract_awardee":None,
            "supplier_verified":False,
            "pq_equipment_only_contract_rub":None,
            "status":"project_procurement_original_contract_unverified",
            "demand_group":x["demand_group"],
            "source_identifier_masked":x["procedure_id"] is None,
            "evidence":[{"url":y["url"],"source_tier":y["tier"],"locator":y["locator"],"excerpt":x["title"]} for y in x["evidence"]],
            "notes":x["notes"],
        }
        items.append(row)
        keys.add(x["canonical_id"])
    if len(items)!=m["total_rows"]:
        raise ValueError("v16 output total changed")
    return {
        **old, "records":items, "data_version":"v16",
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "total_lot_level_records":len(items),
            "new_rows_from_v15":3,
            "production_structured_records_imported":71,
            "new_records_pending_import":16,
            "original_signed_contract_xml_known_count":4,
            "market_population_complete":False,
        },
        "seed_completeness":"Not a full Russian PQ national census",
    }

if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
