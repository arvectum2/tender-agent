"""MI-013 v36: replay all 103 original procurement signals and original buyer pricing."""
import copy,json
from materialize_pq_research_v35 import materialize as v35
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    base=v35()
    rows=copy.deepcopy(base["records"])
    doc=json.loads((DATA/"original_meles_6kv_itemized_cost_and_regime_20261028.v36.json").read_text(encoding="utf-8"))
    patches=doc["patches"]
    if len(patches)!=1 or doc["new_notices"]!=0:
        raise ValueError("v36 one existing case no new notice expected")
    p=patches[0]
    targets=[x for x in rows if x["canonical_id"]==p["canonical_id"]]
    if len(targets)!=1 or "v36" in targets[0].get("mi013_source_enrichments",{}):
        raise ValueError("v36 target source key missing or already enriched")
    targets[0].setdefault("mi013_source_enrichments",{})["v36"]={
        "source_file":"original_meles_6kv_itemized_cost_and_regime_20261028.v36.json",
        "verified_primary":copy.deepcopy(p),
        "source_grade":"first_party_original_ETP_itemized_XLSX_and_TZ"}
    if len(rows)!=103 or len({x["canonical_id"] for x in rows})!=103:
        raise ValueError("v36 must preserve all 103 distinct legal notices")
    return {**base,"records":rows,"data_version":"v36",
       "materialization_manifest":"verified_public_leads_20261028.v36.manifest.json"}

if __name__=="__main__":
    d=materialize()
    out=export_records(d)
    print(json.dumps({"source_version":"v36","records":len(out),
      "unique_ids":len({x["external_id"] for x in out}),
      "enriched_original_records":sum(bool(x.get("mi013_source_enrichments")) for x in d["records"])},
      ensure_ascii=False))
