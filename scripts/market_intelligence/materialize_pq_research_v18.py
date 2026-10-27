"""MI-013 v18 source-backed expansion. No PostgreSQL write or network side effect."""
from __future__ import annotations

import json
from pathlib import Path
from materialize_pq_research_v17 import materialize as parent_materialize

ROOT = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"
MANIFEST = "verified_public_leads_20261027.v18.manifest.json"

def materialize():
    meta = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    delta = json.loads((ROOT / meta["delta_file"]).read_text(encoding="utf-8"))
    original = parent_materialize()
    rows = list(original["records"])
    if len(rows) != meta["base_rows"] or len(delta["records"]) != meta["delta_rows"]:
        raise ValueError("baseline or delta count drift")
    seen = {r["canonical_id"] for r in rows}
    for item in delta["records"]:
        if item["canonical_id"] in seen:
            raise ValueError("duplicate candidate")
        if not meta["period"]["from"] <= item["publication_date"] <= meta["period"]["to"]:
            raise ValueError("date outside rolling window")
        if not item["sources"] or not all(s["url"].startswith("https://") for s in item["sources"]):
            raise ValueError("missing verified URL")
        if item["reported_contract_total_rub"] is not None or item["nmck_rub"] is not None:
            raise ValueError("market enquiry with unverified budget promoted to contract or NMC")
        if item["equipment_voltage_kv"] not in (6.3, 10):
            raise ValueError("unsupported voltage value")
        record = {
            "id": "pq-v18-" + item["canonical_id"].replace(":", "-"),
            "canonical_id": item["canonical_id"],
            "procedure_id": item["procedure_id"],
            "publication_date": item["publication_date"],
            "date_basis": item["date_basis"],
            "procurement_regime": "commercial",
            "platform": "B2B-Center" if item["procedure_id"] else "Rostender catalogue / originating platform unknown",
            "customer": {"name": item["customer"], "inn": item["buyer_inn"]},
            "beneficiary": item["beneficiary"],
            "description": item["title"],
            "project": item["title"],
            "family": item["family"],
            "scope": item["scope"],
            "quantity": item["quantity"],
            "quantity_unit": item["unit"],
            "equipment_model": item["model"],
            "equipment_voltage_kv": item["equipment_voltage_kv"],
            "equipment_reactive_power_mvar": item["mvar_if_model_exact"],
            "nmck_rub": None,
            "reported_contract_total_rub": None,
            "reported_final_price_rub": None,
            "supplier_verified": False,
            "supplier_inn": None,
            "pq_equipment_only_contract_rub": None,
            "demand_group": item["demand_group"],
            "deadline_date": item["deadline_date"],
            "source_identifier_masked": item["procedure_id"] is None,
            "status": "market_price_survey_or_supply_original_award_unverified",
            "evidence": [
                {"url": s["url"], "source_tier": item["source_tier"], "locator": s["role"]}
                for s in item["sources"]
            ],
            "market_scope": "6_35kv_nominated_equipment_line_only_not_revenue",
            "notes": item["notes"],
        }
        seen.add(item["canonical_id"])
        rows.append(record)
    if len(rows) != meta["total_rows"] or len(seen) != len(rows):
        raise ValueError("new source count drift")
    return {
        **original, "records": rows, "data_version": "v18",
        "materialization_manifest": MANIFEST,
        "verification_summary": {
            "total_lot_level_records": len(rows),
            "production_structured_records_imported": 71,
            "new_records_pending_import": 30,
            "new_original_signed_contracts": 0,
            "national_market_census_complete": False,
        },
        "seed_completeness": "A source-linked discovery corpus, not a full Russian procurement census",
    }

if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
