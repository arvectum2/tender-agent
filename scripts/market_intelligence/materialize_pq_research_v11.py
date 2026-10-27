"""Read-only deterministic MI-013 v11: 68 baseline records + 3 lot-level leads."""
from __future__ import annotations

import json
from pathlib import Path
from materialize_pq_research_v10 import materialize as materialize_v10

DATA = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"
MANIFEST = "verified_public_leads_20261027.v11.manifest.json"


def materialize():
    spec = json.loads((DATA / MANIFEST).read_text(encoding="utf-8"))
    prev = materialize_v10()
    delta = json.loads((DATA / spec["append_dataset"]).read_text(encoding="utf-8"))
    if len(prev["records"]) != spec["base_lot_level_records"]:
        raise ValueError("baseline count drift")
    if len(delta["records"]) != spec["append_lot_level_records"]:
        raise ValueError("increment count drift")
    if len(set(r["procedure_id"] for r in delta["records"])) != spec["additional_unique_eis_notice_numbers"]:
        raise ValueError("notices and lots confused")
    rows = list(prev["records"])
    canonical = {r["canonical_id"] for r in rows}
    if len(canonical) != len(rows):
        raise ValueError("baseline duplicate")
    lots = [r for r in delta["records"] if r["procedure_id"] == "32616474682"]
    if len(lots) != 2 or {r["lot_number"] for r in lots} != {1, 2}:
        raise ValueError("joint EIS tender must have exactly two lots")
    if sum(int(round(float(r["nmck_rub"]) * 100)) for r in lots) != 245265041:
        raise ValueError("joint lot NMC do not match published 2452650.41 RUB")
    if any(r["joint_notice_nmck_ex_vat_rub"] != "2452650.41" for r in lots):
        raise ValueError("incorrect parent NMC")
    if len({r["buyer_inn"] for r in lots}) != 2:
        raise ValueError("lost buyer distinction")
    for raw in delta["records"]:
        cid = raw["canonical_id"]
        if cid in canonical:
            raise ValueError("duplicate lot canonical ID: " + cid)
        if raw.get("supplier_verified") or raw.get("contract_total_rub") is not None:
            raise ValueError("cannot assert award without original signed record")
        if not raw["evidence"] or not all(x["url"].startswith("https://") for x in raw["evidence"]):
            raise ValueError("invalid provenance")
        if raw.get("equipment_voltage_kv") is not None:
            raise ValueError("new equipment rated voltage not verified")
        item = {
            "id": "pq-" + raw["procedure_id"] + "-lot" + str(raw["lot_number"]),
            "canonical_id": cid,
            "publication_date": raw["publication_date"],
            "date_basis": "published_original_etp" if raw["procedure_id"] == "32616474682" else "secondary_amendment_log",
            "procedure_id": raw["procedure_id"],
            "platform": "B2B-Center / EIS 223-FZ" if raw["procedure_id"] == "32616474682" else "ЕЭТП / ЕИС 223-ФЗ",
            "procurement_regime": "223-fz",
            "customer": {"name": raw["buyer"], "inn": raw["buyer_inn"]},
            "organizer": {"name": raw["organizer"], "inn": raw["organizer_inn"]},
            "beneficiary": None,
            "project": raw["project"],
            "family": raw["family"],
            "scope": raw["scope"],
            "description": raw["description"],
            "quantity": raw["quantity"],
            "quantity_unit": raw["quantity_unit"],
            "nmck_rub": raw["nmck_rub"],
            "reported_price_kind": raw["reported_price_kind"],
            "status": raw["status"],
            "evidence": raw["evidence"],
            "notes": raw["notes"],
            "lot_number": raw["lot_number"],
            "joint_notice_id": raw["procedure_id"],
            "equipment_voltage_kv": None,
            "market_scope": "voltage_unverified_not_strict_6_35kv",
            "supplier_verified": False,
            "supplier_inn": None,
            "reported_contract_total_rub": None,
            "pq_equipment_only_contract_rub": None,
        }
        if raw.get("joint_notice_nmck_ex_vat_rub"):
            item["joint_notice_nmck_ex_vat_rub"] = raw["joint_notice_nmck_ex_vat_rub"]
        if raw.get("published_deadline_current"):
            item["bid_deadline_current"] = raw["published_deadline_current"]
            item["nmck_original_rub"] = raw["initial_nmck_original_rub"]
        rows.append(item)
        canonical.add(cid)
    if len(rows) != spec["total_lot_level_records"] or len(canonical) != len(rows):
        raise ValueError("total lot-level count changed")
    return {
        **prev,
        "records": rows,
        "data_version": "v11",
        "materialization_manifest": MANIFEST,
        "seed_completeness": "discovered_examples_only_not_population",
        "verification_summary": {
            "prior_lot_level_records": 68,
            "new_lot_level_records": 3,
            "total_lot_level_records": 71,
            "additional_unique_eis_notice_numbers": 2,
            "joint_notice_lot_count": 2,
            "new_confirmed_awarded_contracts": 0,
            "new_signed_contract_revenue_rub": "0",
        },
        "delta_note": "Three additional lot-level observations represent TWO EIS notices. Neither has signed award; large 452m initial price must not be confused with target 6-35kV revenue.",
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
