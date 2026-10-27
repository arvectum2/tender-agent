"""Materialize PQ v9: baseline v8 research records + 4 sourced 2025 EIS leads."""
from __future__ import annotations
import json
from pathlib import Path
from materialize_pq_research import materialize as materialize_v8

DATA = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"
MANIFEST = "verified_public_leads_20261027.v9.manifest.json"

def materialize():
    spec = json.loads((DATA / MANIFEST).read_text(encoding="utf-8"))
    base = materialize_v8()
    append = json.loads((DATA / spec["append_dataset"]).read_text(encoding="utf-8"))
    if len(base["records"]) != spec["base_count"] or len(append["records"]) != spec["append_count"]:
        raise ValueError("PQ source count drift")
    rows = list(base["records"])
    ids = {r["canonical_id"] for r in rows}
    if len(ids) != len(rows):
        raise ValueError("baseline duplicate")
    for raw in append["records"]:
        cid = raw["canonical_id"]
        if cid in ids:
            raise ValueError("duplicate canonical procedure: " + cid)
        if not raw["source_url"].startswith("https://") or raw["nmck_rub"] is None:
            raise ValueError("missing financial or source provenance")
        if raw["registered_contract_verified"] or raw["award_winner_verified"] or raw["official_tz_verified"]:
            raise ValueError("unjustified primary procurement status")
        row = {
            "id": "pq-2025-rosseti-" + raw["procedure_id"],
            "canonical_id": cid,
            "publication_date": raw["publication_date"],
            "date_basis": "published_secondary_index",
            "deadline_date": raw["deadline_date"],
            "procedure_id": raw["procedure_id"],
            "platform": "EIS 223-FZ / RTS-Tender (public indexed listing)",
            "procurement_regime": "223-fz",
            "customer": {"name": raw["customer"], "inn": None},
            "beneficiary": None,
            "project": raw["project"],
            "family": raw["family"],
            "scope": raw["scope"],
            "description": raw["description"],
            "quantity": None,
            "quantity_unit": None,
            "nmck_rub": raw["nmck_rub"],
            "reported_price_kind": raw["reported_price_kind"],
            "status": "secondary_procurement_listing_original_protocol_pending",
            "evidence": [{
                "url": raw["source_url"],
                "source_tier": "third_party_indexed_original_procurement_number",
                "locator": raw["support"],
                "excerpt": raw["description"],
            }],
            "notes": raw["notes"],
            "equipment_voltage_kv": None,
            "market_scope": raw["market_scope"],
            "supplier_verified": False,
            "pq_equipment_only_contract_rub": None,
            "linked_contract_registry_number": None,
            "reported_contract_total_rub": None,
        }
        rows.append(row)
        ids.add(cid)
    if len(rows) != spec["total_count"]:
        raise ValueError("PQ total count drift")
    return {
        **base,
        "records": rows,
        "data_version": "v9",
        "materialization_manifest": MANIFEST,
        "verification_summary": {
            "prior_records": spec["base_count"],
            "added_records": len(append["records"]),
            "total_records": len(rows),
            "added_ids": [x["procedure_id"] for x in append["records"]],
            "primary_new_contract_count": 0,
            "new_nmc_sum_rub_not_market_value": "90672176",
        },
        "delta_note": "v9 adds four 2025 223-FZ leads as secondary source records, not signed contracts or primary-protocol verified. 220kV is substation rating, not PQ device rating.",
    }

if __name__ == "__main__":
    import sys
    sys.stdout.write(json.dumps(materialize(), ensure_ascii=False, sort_keys=True, indent=2) + "\n")
