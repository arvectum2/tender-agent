"""MI-013 v19: retract unsupported second Mogocha tender and enrich existing lots.

No database writes. Explicit correction file retains the full history,
including why one previously counted 2024 tender is not separately evidenced.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from materialize_pq_research_v18 import materialize as v18

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v19.manifest.json"


def materialize() -> dict:
    config=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    delta=json.loads((DATA/config["correction_file"]).read_text(encoding="utf-8"))
    baseline=v18()
    original=baseline["records"]
    if len(original)!=config["base_rows"] or len(original)!=delta["expected_parent_count"]:
        raise ValueError("v18 baseline unexpected")
    if len(delta["remove"])!=config["retracted_unsupported_rows"]:
        raise ValueError("unexpected removal count")
    if len(delta["enrich"])!=config["existing_record_enrichments"]:
        raise ValueError("unexpected correction count")
    old_ids=[r["canonical_id"] for r in original]
    if len(set(old_ids))!=len(old_ids):
        raise ValueError("duplicate original source IDs")
    excluded={r["canonical_id"] for r in delta["remove"]}
    updates={r["canonical_id"]:r for r in delta["enrich"]}
    if len(excluded)!=len(delta["remove"]) or len(updates)!=len(delta["enrich"]):
        raise ValueError("duplicate correction targets")
    if not (excluded|set(updates)).issubset(set(old_ids)):
        raise ValueError("correction target missing from v18")
    if excluded & set(updates):
        raise ValueError("record cannot be both removed and updated")
    rows=[]
    for record in original:
        cid=record["canonical_id"]
        if cid in excluded:
            continue
        row=copy.deepcopy(record)
        if cid in updates:
            patch=updates[cid]
            if any(key in {"id","canonical_id","procedure_id","publication_date","nmck_rub","reported_contract_total_rub","supplier_verified"} for key in patch["fields"]):
                raise ValueError("cannot silently edit identifier, money or signed-contract status")
            row.update(patch["fields"])
            row["evidence"]=row.get("evidence",[])+patch.get("evidence_append",[])
            row["notes"]=(row.get("notes") or "")+patch.get("notes_append","")
        rows.append(row)
    if len(rows)!=config["active_rows"] or len({r["canonical_id"] for r in rows})!=len(rows):
        raise ValueError("v19 active denominator mismatch")
    if [r["canonical_id"] for r in rows]!=[x for x in old_ids if x not in excluded]:
        raise ValueError("unexpected source order or identity rewrite")
    if not all(x in {r["canonical_id"] for r in rows} for x in [
        "223fz:32313008364:lot1","commercial:106044-ТТ:lot1","commercial:РН41205245:lot1"
    ]):
        raise ValueError("existing primary legal notices lost")
    return {
        **baseline,
        "records":rows,
        "data_version":"v19",
        "materialization_manifest":MANIFEST,
        "retracted_observations":delta["remove"],
        "verification_summary":{
            "total_lot_level_records":len(rows),
            "retracted_false_duplicate_count":len(excluded),
            "enriched_existing_records":len(updates),
            "production_structured_records_imported":71,
            "new_records_pending_import":len(rows)-71,
            "original_registered_contracts_from_Rd223":4,
            "market_population_complete":False,
        },
        "seed_completeness":"Not a complete national procurement census; retracted false Mogocha second 2024 service observation is retained in correction audit trail",
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
