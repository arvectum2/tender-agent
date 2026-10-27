"""Reproduce all 102 MI013 rows including source-grade secondary Novatek BOM."""
import copy
import json
from materialize_pq_research_v33 import materialize as v33
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    d=v33()
    a=copy.deepcopy(d["records"])
    patch=json.loads((DATA/"secondary_etgpb_novatek_bom_20261027.v34.json").read_text(encoding="utf-8"))["patches"]
    if len(patch)!=1 or patch[0]["canonical_id"]!="commercial:ГП630876:lot1":
        raise ValueError("v34 one existing case expected")
    source=[x for x in a if x["canonical_id"]==patch[0]["canonical_id"]]
    if len(source)!=1 or "v34" in source[0].get("mi013_source_enrichments",{}):
        raise ValueError("v34 identity duplicated or source evidence already changed")
    source[0].setdefault("mi013_source_enrichments",{})["v34"]={
        "source_file":"secondary_etgpb_novatek_bom_20261027.v34.json",
        "verified_secondary":copy.deepcopy(patch[0]),
        "source_grade":"secondary_platform_reprint_not_primary_archive"}
    if len(a)!=102 or len({x["canonical_id"] for x in a})!=102:
        raise ValueError("v34 must not add legal notices")
    return {**d,"data_version":"v34","records":a,
            "materialization_manifest":"verified_public_leads_20261027.v34.manifest.json"}

if __name__=="__main__":
    ds=materialize()
    r=export_records(ds)
    print(json.dumps({"source_version":"v34","notices":len(r),
        "unique":len({x["external_id"] for x in r}),
        "enriched":sum(bool(x.get("mi013_source_enrichments")) for x in ds["records"])},
        ensure_ascii=False))
