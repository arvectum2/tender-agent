"""Rebuild MI-013 102-source corpus from v29 and original append-only evidence."""
import copy
import json
from import_pq_postgres_v29 import materialize_v29, DATA
from export_pq_data_platform import export_records

def materialize():
    base = materialize_v29()
    items = copy.deepcopy(base["records"])
    lookup = {item["canonical_id"]: item for item in items}
    if len(lookup) != 101: raise ValueError("expected 101 original procurement IDs")
    for version,filename,key,expected in [
        ("v31","primary_2024_khani_epc_original_award_20261027.v31.json","patches",1),
        ("v32","primary_sibsteklo_turan_docs_20261027.v32.json","source_patches",2),
    ]:
        patches = json.loads((DATA/filename).read_text(encoding="utf-8"))[key]
        if len(patches) != expected: raise ValueError("original evidence count mismatch")
        for patch in patches:
            record = lookup[patch["canonical_id"]]
            record.setdefault("mi013_source_enrichments", {})[version] = {
                "source_file": filename, "verified_original": copy.deepcopy(patch)
            }
    extra = json.loads((DATA/"original_b2b_capacitor_vtu_20261027.v33.json").read_text(encoding="utf-8"))["records"]
    if len(extra)!=1 or extra[0]["canonical_id"] in lookup: raise ValueError("bad new notice")
    if extra[0]["original_bids_submitted"] != 0 or extra[0]["commission_winner"] is not None:
        raise ValueError("invalid winning-bid classification")
    items.extend(copy.deepcopy(extra))
    if len(items)!=102 or len({r["canonical_id"] for r in items})!=102:
        raise ValueError("expected 102 distinct notices")
    return {**base,"data_version":"v33","records":items,
        "materialization_manifest":"verified_public_leads_20261027.v33.manifest.json",
        "verification_summary":{"total_lot_level_records":102,"market_population_complete":False}}

if __name__=="__main__":
    corpus=materialize()
    exported=export_records(corpus)
    print(json.dumps({"notices":len(exported),"unique_ids":len({r["external_id"] for r in exported}),
        "source_enriched":sum(bool(r.get("mi013_source_enrichments")) for r in corpus["records"])},
        ensure_ascii=False))
