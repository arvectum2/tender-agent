"""Deterministically join PQ v7 source data with archived corporate notice delta.

Never calls network services or writes to production systems.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[2] / "data/market_intelligence/power_quality"


def _read(name: str) -> dict[str, Any]:
    if Path(name).name != name:
        raise ValueError("dataset reference must be a basename")
    result = json.loads((DATA / name).read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("expected object")
    return result


def materialize() -> dict[str, Any]:
    manifest_name = "verified_public_leads_20261027.v8.manifest.json"
    manifest = _read(manifest_name)
    base = _read(manifest["base_dataset"])
    extra = _read(manifest["append_dataset"])
    before, delta = base["records"], extra["records"]
    if len(before) != manifest["base_record_count"]:
        raise ValueError("baseline count drift")
    if len(delta) != manifest["append_record_count"]:
        raise ValueError("source delta count drift")
    ids = {record["canonical_id"] for record in before}
    if len(ids) != len(before):
        raise ValueError("duplicate in baseline")
    merged = list(before)
    for raw in delta:
        cid = raw["canonical_id"]
        if cid in ids:
            raise ValueError(f"duplicate canonical ID {cid}")
        if raw["publication_date"] is not None or not raw.get("deadline_date"):
            raise ValueError("submission deadline is not publication date")
        if not raw["source_url"].startswith("https://"):
            raise ValueError("invalid source")
        if any(raw.get(k) is not None for k in ("nmck_rub", "contract_rub", "winner")):
            raise ValueError("unverified price or winner")
        voltages = raw.get("equipment_voltage_kv_set") or [raw["equipment_voltage_kv"]]
        if not voltages or any(v not in (6, 10, 35) for v in voltages):
            raise ValueError("out-of-scope voltage")
        row = {
            "id": "pq-" + raw["procedure_id"].lower().replace("/", "-"),
            "canonical_id": cid,
            "publication_date": None,
            "date_basis": "deadline_only_not_publication",
            "deadline_date": raw["deadline_date"],
            "procedure_id": raw["procedure_id"],
            "platform": "UDSgroup corporate tender archive",
            "procurement_regime": "commercial",
            "customer": {"name": raw["customer"], "inn": None},
            "beneficiary": None,
            "project": "UDSgroup oil supplies, Udmurtia",
            "family": "capacitor_bank",
            "scope": "supply",
            "description": raw["item"],
            "quantity": None,
            "quantity_unit": None,
            "nmck_rub": None,
            "reported_price_kind": None,
            "status": "corporate_archive_indexed_award_unverified",
            "evidence": [{
                "url": raw["source_url"],
                "source_tier": raw["source_tier"],
                "locator": "corporate archive indexed notice " + raw["procedure_id"],
                "excerpt": raw["item"],
            }],
            "notes": (
                "Archived corporate index only. Date is bid deadline, not published date. "
                "Exact buying legal entity, award, quantity, NMC and contract unverified."
            ),
            "equipment_voltage_kv": voltages[0] if len(voltages) == 1 else None,
            "equipment_voltage_kv_set": voltages,
            "market_scope": "target_6_to_10kv_model_in_corporate_archive",
        }
        merged.append(row)
        ids.add(cid)
    if len(merged) != manifest["total_procedure_count"] or len(ids) != len(merged):
        raise ValueError("invalid merged count or duplicate key")
    return {
        **base,
        "records": merged,
        "supersedes": manifest["base_dataset"],
        "data_version": manifest["data_version"],
        "materialization_manifest": manifest_name,
        "seed_completeness": "discovered_examples_only_not_population",
        "delta_note": "58 prior records unchanged; 2 corporate archived BSK 6/10 kV notices; no contract inference.",
        "verification_summary": {
            "prior_records": len(before),
            "added_records": len(delta),
            "total_records": len(merged),
            "added_ids": [item["procedure_id"] for item in delta],
            "added_confirmed_winners": 0,
            "added_confirmed_contract_rub": "0",
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    text = json.dumps(materialize(), ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
