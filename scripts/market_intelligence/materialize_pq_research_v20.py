"""MI-013: append original protocol bidder evidence without inventing signed vendor.

v20 enriches five existing canonical cases only. Does not write to production.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from materialize_pq_research_v19 import materialize as v19

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v20.manifest.json"


def materialize():
    m=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    changes=json.loads((DATA/m["protocol_evidence_file"]).read_text(encoding="utf-8"))
    baseline=v19()
    old=baseline["records"]
    if len(old)!=m["base_rows"] or len(changes["patches"])!=m["existing_records_enriched"]:
        raise ValueError("base corpus or evidence count unexpectedly changed")
    lookup={x["canonical_id"]:x for x in changes["patches"]}
    ids={x["canonical_id"] for x in old}
    if len(ids)!=len(old) or not set(lookup).issubset(ids) or len(lookup)!=len(changes["patches"]):
        raise ValueError("original source target identity drift")
    out=[]
    for original in old:
        row=copy.deepcopy(original)
        cid=row["canonical_id"]
        if cid in lookup:
            new=lookup[cid]
            if not all(x["url"].startswith("https://") and (x.get("sha256") or x["tier"].startswith("independent_secondary")) for x in new["source_evidence"]):
                raise ValueError("missing original source certificate")
            if any(x in new["fields"] for x in ("canonical_id","procedure_id","nmck_rub","publication_date","supplier_verified","scope","family")):
                raise ValueError("attempt to overwrite stable procurement facts")
            if new["fields"].get("original_registry_supplier_identity_verified") is True:
                raise ValueError("redacted RD223 cannot verify supplier")
            if new["fields"].get("original_protocol_named_bidder") and new["fields"].get("original_protocol_bidder_role") is None:
                raise ValueError("named vendor requires bidder role")
            if new["fields"].get("original_protocol_ukrm_min_mvar",0)>0 and new["fields"].get("equipment_cost_is_signed_sale") is not False:
                raise ValueError("2025 budget cannot be promoted to 2026 contracted device price")
            row["protocol_role_evidence"]=copy.deepcopy(new["fields"])
            row["protocol_role_interpretation"]=new["interpretation"]
            row["protocol_role_original_sources"]=new["source_evidence"]
        out.append(row)
    if len(out)!=m["total_active_rows"] or [x["canonical_id"] for x in out]!=[x["canonical_id"] for x in old]:
        raise ValueError("v20 changed number/order of procurement notices")
    return {
        **baseline,
        "data_version":"v20",
        "records":out,
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "total_lot_level_records":len(out),
            "existing_records_with_new_primary_protocol_data":len(lookup),
            "new_notices_added":0,
            "named_tender_bidders_in_addendum":sum(
                bool(p["fields"].get("original_protocol_named_bidder"))
                for p in changes["patches"]
            ),
            "signed_contract_supplier_identity_newly_verified":0,
            "total_original_Rd223_signed_contracts":4,
            "production_structured_records_imported":71,
            "new_records_pending_import":29,
            "market_population_complete":False,
        },
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
