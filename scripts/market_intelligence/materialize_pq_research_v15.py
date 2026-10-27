"""Version 15 research-only procurement ledger: 84 observations and reissue grouping.

Adds one confirmed-cancelled 2026 EIS notice and one 2024 signed-contract
lead with the EIS ID deliberately masked by its public source.
Never writes to production Data Platform; v12's 71 rows stay unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from materialize_pq_research_v14 import materialize as v14

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v15.manifest.json"


def materialize():
    spec=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    delta=json.loads((DATA/spec["delta_file"]).read_text(encoding="utf-8"))
    old=v14()
    rows=list(old["records"])
    if len(rows)!=spec["base_rows"] or len(delta["records"])!=spec["delta_rows"]:
        raise ValueError("v15 source count drift")
    existing={r["canonical_id"] for r in rows}
    if len(existing)!=len(rows):
        raise ValueError("v14 contains duplicate canonical IDs")
    for raw in delta["records"]:
        if raw["canonical_id"] in existing:
            raise ValueError("new source already exists: "+raw["canonical_id"])
        if not (spec["period"]["from"]<=raw["publication_date"]<=spec["period"]["to"]):
            raise ValueError("discovery outside analysis period")
        if not raw["evidence"] or any(not e["url"].startswith("https://") for e in raw["evidence"]):
            raise ValueError("source URL invalid")
        if raw["scope"]=="supply" and raw.get("reported_contract_total_rub") is not None:
            if not raw.get("contract_source_tier","").startswith("secondary"):
                raise ValueError("unsigned contract upgraded to original")
        if raw.get("procedure_result")=="CANCELLED" and raw.get("reported_contract_total_rub") is not None:
            raise ValueError("cancelled tender must not claim signed award")
        rec={
            "id":"pq-v15-"+(raw.get("procedure_id") or raw["source_id"]),
            "canonical_id":raw["canonical_id"],
            "procedure_id":raw.get("procedure_id"),
            "publication_date":raw["publication_date"],
            "date_basis":"secondary_published_procurement_listing",
            "procurement_regime":"223-fz",
            "platform":"public indexed EIS tender",
            "customer":{"name":raw["buyer"],"inn":raw["buyer_inn"]},
            "description":raw["title"],
            "project":raw["title"],
            "family":raw["family"],
            "scope":raw["scope"],
            "equipment_voltage_kv":raw["equipment_voltage_kv"],
            "quantity":raw.get("quantity"),
            "quantity_unit":raw.get("unit"),
            "nmck_rub":raw["nmck_rub"],
            "reported_price_kind":raw["nmck_kind"],
            "reported_contract_total_rub":raw.get("reported_contract_total_rub"),
            "reported_contract_total_source_tier":raw.get("contract_source_tier"),
            "reported_contract_date":raw.get("reported_contract_date"),
            "supplier_verified":False,
            "supplier_inn":None,
            "pq_equipment_only_contract_rub":None,
            "status":raw["procedure_result"],
            "demand_group":raw["demand_group"],
            "potential_same_demand_as":raw.get("same_demand_as",[]),
            "source_identifier_masked":raw.get("procedure_id") is None,
            "market_scope":"PQ equipment nominal voltage unknown; not strict 6-35kV",
            "evidence":raw["evidence"],
            "notes":raw["notes"],
        }
        rows.append(rec)
        existing.add(rec["canonical_id"])
    if len(rows)!=spec["total_rows"]:
        raise ValueError("v15 materialization count mismatch")
    return {
        **old,
        "records":rows,
        "data_version":"v15",
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "base_lot_level_records":82,
            "added_lot_level_records":2,
            "total_lot_level_records":84,
            "newly_verified_primary_awarded_contracts":0,
            "original_signed_contract_xml_known_count":4,
            "production_structured_records_imported":71,
            "new_records_pending_import":13,
            "market_population_complete":False,
        },
        "seed_completeness":"NOT all 2023-26 Russian PQ procurement notices; public-source evidence only",
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
