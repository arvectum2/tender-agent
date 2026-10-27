"""Deterministically merge MI-013 v9 with three evidence-linked procurement attempts.
Read-only; no database access or side effects except stdout in CLI mode.
"""
from __future__ import annotations

import json
from pathlib import Path
from materialize_pq_research_v9 import materialize as materialize_v9

DATA = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"
MANIFEST = "verified_public_leads_20261027.v10.manifest.json"


def materialize() -> dict:
    manifest = json.loads((DATA / MANIFEST).read_text(encoding="utf-8"))
    old = materialize_v9()
    new = json.loads((DATA / manifest["append_dataset"]).read_text(encoding="utf-8"))
    if len(old["records"]) != manifest["base_count"]:
        raise ValueError("baseline record count drift")
    if len(new["records"]) != manifest["append_count"]:
        raise ValueError("incremental record count drift")
    rows = list(old["records"])
    ids = {r["canonical_id"] for r in rows}
    if len(ids) != len(rows):
        raise ValueError("duplicate baseline IDs")

    for raw in new["records"]:
        if raw["canonical_id"] in ids:
            raise ValueError("duplicate purchase " + raw["canonical_id"])
        if any(not link["url"].startswith("https://") for link in raw["sources"]):
            raise ValueError("source link malformed")
        if raw["supplier_verified"] or raw["supplier_inn"] is not None:
            raise ValueError("award/supplier not verified by original contract")
        if raw["equipment_voltage_kv"] is None and not raw["market_scope"].startswith("adjacent"):
            raise ValueError("voltage not grounded for strict 6-35kV")
        if raw["scope"] == "design" and raw.get("equipment_reactive_power_mvar_total") == 52:
            if raw.get("equipment_voltage_kv") is not None:
                raise ValueError("110kV substation does not confirm nominal voltage of replacement SKRM")
        item = {
            "id": "pq-" + raw["procedure_id"],
            "canonical_id": raw["canonical_id"],
            "publication_date": raw["publication_date"],
            "date_basis": "secondary_public_procurement_index",
            "procedure_id": raw["procedure_id"],
            "platform": raw["platform"],
            "procurement_regime": "223-fz",
            "customer": {"name": raw["buyer"], "inn": raw["buyer_inn"]},
            "beneficiary": None,
            "project": raw["project"],
            "family": raw["family"],
            "scope": raw["scope"],
            "description": raw["title"],
            "quantity": raw["quantity"],
            "quantity_unit": raw["quantity_unit"],
            "nmck_rub": raw["nmck_rub"],
            "reported_price_kind": "initial_price_not_contract",
            "status": (
                "secondary_signed_contract_after_one_bid_failed_procedure"
                if raw.get("reported_signed_contract_rub") is not None
                else "procurement_indexed_no_primary_signed_contract_verified"
            ),
            "evidence": [{
                "url": e["url"],
                "source_tier": e["tier"],
                "locator": e["locator"],
                "excerpt": raw["title"],
            } for e in raw["sources"]],
            "notes": raw["notes"],
            "equipment_voltage_kv": raw["equipment_voltage_kv"],
            "equipment_reactive_power_mvar_total": raw["equipment_reactive_power_mvar_total"],
            "market_scope": raw["market_scope"],
            "demand_group": raw["demand_group"],
            "potential_same_demand_as": raw.get("related_procedure_ids", []),
            "reported_contract_total_rub": raw.get("reported_signed_contract_rub"),
            "reported_contract_total_source_tier": raw.get("contract_source_tier"),
            "linked_contract_registry_number": raw.get("contract_registry_number"),
            "reported_contract_date": raw.get("reported_contract_date"),
            "supplier_verified": False,
            "supplier_inn": None,
            "pq_equipment_only_contract_rub": None,
        }
        rows.append(item)
        ids.add(raw["canonical_id"])
    if len(rows) != manifest["total_count"] or len(ids) != len(rows):
        raise ValueError("bad final count")
    return {
        **old,
        "records": rows,
        "data_version": "v10",
        "materialization_manifest": MANIFEST,
        "verification_summary": {
            "prior_records": len(old["records"]),
            "added_records": len(new["records"]),
            "total_records": len(rows),
            "new_initial_prices_known_count": 3,
            "new_contract_outcomes_reported_secondary": 2,
            "new_contract_outcomes_verified_original_rd223": 0,
            "newly_confirmed_equipment_only_sales_rub": "0",
        },
        "seed_completeness": "discovered_examples_only_not_population",
        "delta_note": (
            "64 earlier IDs preserved + 3 EIS procurements: one contracted 10kV BSK EPC "
            "and 2 separate attempted PИР procurement notices within same Tyazhinskaya 52Mvar project. "
            "Do not count repeat design tenders as independent installed systems."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
