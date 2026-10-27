"""Research-only v13 materializer. Eight new public EIS/ETP leads, no DB writes.

Preserves exact v12 source records and avoids counting design retenders as sales.
"""
from __future__ import annotations

import json
from pathlib import Path

from materialize_pq_research_v12 import materialize as v12

DATA = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"
MANIFEST = "verified_public_leads_20261027.v13.manifest.json"


def materialize() -> dict:
    m = json.loads((DATA / MANIFEST).read_text(encoding="utf-8"))
    delta = json.loads((DATA / m["delta"]).read_text(encoding="utf-8"))
    older = v12()
    if len(older["records"]) != m["base_lot_level_rows"]:
        raise ValueError("v12 count drift")
    if len(delta["records"]) != m["delta_lot_level_rows"]:
        raise ValueError("delta count drift")
    rows = list(older["records"])
    observed = {x["canonical_id"] for x in rows}
    if len(observed) != len(rows):
        raise ValueError("v12 duplicate canonical IDs")
    for raw in delta["records"]:
        if raw["id"] in observed:
            raise ValueError("duplicate ID: " + raw["id"])
        if not raw["source"].startswith("https://"):
            raise ValueError("unlinked public original source")
        if not m["rolling_window"]["from"] <= raw["published"] <= m["rolling_window"]["to"]:
            raise ValueError("publication outside requested rolling 3y")
        if raw.get("scope") == "design" and raw.get("contract_rub") is not None:
            if raw.get("contract_source_grade") is None:
                raise ValueError("unverified signed contract inflated")
        norm = {
            "id": "pq-v13-" + raw["notice"],
            "canonical_id": raw["id"],
            "procedure_id": raw["notice"],
            "publication_date": raw["published"],
            "date_basis": "published_public_procurement_index",
            "procurement_regime": raw["regime"],
            "platform": raw["platform"],
            "customer": {"name": raw["buyer"], "inn": raw["inn"]},
            "project": raw["title"],
            "family": raw["category"],
            "scope": raw["scope"],
            "description": raw["subject"],
            "nmck_rub": raw["nmc_rub"],
            "reported_price_kind": "initial_price_unknown_vat" if raw["nmc_rub"] is not None else None,
            "reported_contract_total_rub": raw.get("contract_rub"),
            "reported_contract_total_source_tier": raw.get("contract_source_grade"),
            "linked_contract_registry_number": raw.get("contract_registry"),
            "reported_contract_date": raw.get("contract_date"),
            "equipment_voltage_kv": raw["voltage_kv"],
            "equipment_reactive_power_mvar": raw["mvar"],
            "market_scope": ("outside_strict_6_35kv" if raw.get("voltage_kv") and raw["voltage_kv"] > 35
                             else "tech_voltage_unknown" if raw.get("voltage_kv") is None
                             else "within_6_35kv_equipment_voltage"),
            "quantity": None,
            "quantity_unit": None,
            "deadline_date": raw.get("deadline"),
            "demand_group": raw.get("project"),
            "related_procedures": raw.get("related", []),
            "status": "public_notice_original_award_unverified",
            "supplier_verified": False,
            "supplier_inn": None,
            "pq_equipment_only_contract_rub": None,
            "evidence": [
                {"url": raw["source"], "source_tier": raw["grade"], "locator": raw["title"], "excerpt": raw["subject"]},
            ],
            "notes": raw["notes"],
        }
        if raw.get("supporting_source"):
            norm["evidence"].append({
                "url": raw["supporting_source"], "source_tier": "third_party_cross_check",
                "locator": raw["notice"], "excerpt": raw["subject"],
            })
        rows.append(norm)
        observed.add(raw["id"])
    if len(rows) != m["total_lot_level_rows"]:
        raise ValueError("v13 row count drift")
    return {
        **older,
        "records": rows,
        "data_version": "v13",
        "materialization_manifest": MANIFEST,
        "verification_summary": {
            "base_lot_level_records": m["base_lot_level_rows"],
            "added_lot_level_records": m["delta_lot_level_rows"],
            "total_lot_level_records": len(rows),
            "new_primary_verified_award_count": 0,
            "new_secondary_reported_contract_count": sum(bool(x.get("contract_rub")) for x in delta["records"]),
            "new_independently_signed_equipment_sale_count": 0,
            "production_structured_records_imported": 71,
            "new_records_pending_import": 8,
        },
        "seed_completeness": "NOT a complete Russian market census: inaccessible/undiscovered commercial ETP and nested EPC protocols remain",
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
