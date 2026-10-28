"""MI013 v40 full source replay of 104 notices including Karelia 35kV primary protocols."""
import copy,json
from materialize_pq_research_v39 import materialize as old
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    base=old()
    rows=copy.deepcopy(base["records"])
    f="original_karelia_35kv_commission_20261028.v40.json"
    doc=json.loads((DATA/f).read_text(encoding="utf8"))
    if doc["new_procurement_notices"]!=0 or doc["existing_cases_enriched"]!=1 or len(doc["patches"])!=1:
        raise ValueError("must enrich one existing original notice only")
    p=doc["patches"][0]
    matches=[r for r in rows if r["canonical_id"]==p["canonical_id"]]
    if len(matches)!=1 or "v40" in matches[0].get("mi013_source_enrichments",{}):
        raise ValueError("notice missing or source already enriched")
    matches[0].setdefault("mi013_source_enrichments",{})["v40"]={
        "source_file":f,"verified_primary":copy.deepcopy(p),
        "source_grade":"original_EIS_35kv_turnkey_EPC_commission_two_archive"}
    if len(rows)!=104 or len({r["canonical_id"] for r in rows})!=104:
        raise ValueError("canonical notices changed unexpectedly")
    return {**base,"records":rows,"data_version":"v40",
            "materialization_manifest":"verified_public_leads_20261028.v40.manifest.json"}

if __name__=="__main__":
    ds=export_records(materialize())
    print(json.dumps({"source":"v40","rows":len(ds),"unique":len({x["external_id"] for x in ds})}))
