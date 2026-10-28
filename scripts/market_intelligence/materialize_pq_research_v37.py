"""Deterministically replay the 103-source MI-013 corpus through original 24 BSK components v37."""
import copy,json
from materialize_pq_research_v36 import materialize as v36
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    base=v36()
    rows=copy.deepcopy(base["records"])
    f="original_rosseti_24_bsk_caps_20261028.v37.json"
    source=json.loads((DATA/f).read_text(encoding="utf-8"))
    if source["new_procurement_notices"]!=0 or source["existing_cases_enriched"]!=1 or len(source["patches"])!=1:
        raise ValueError("v37 adds evidence to one original legal notice only")
    patch=source["patches"][0]
    targets=[r for r in rows if r["canonical_id"]==patch["canonical_id"]]
    if len(targets)!=1 or "v37" in targets[0].get("mi013_source_enrichments",{}):
        raise ValueError("v37 target original missing or duplicate")
    targets[0].setdefault("mi013_source_enrichments",{})["v37"]={
       "source_file":f,"verified_primary":copy.deepcopy(patch),
       "source_grade":"first_party_original_ETP_itemized_XLSX_and_TZ"}
    if len(rows)!=103 or len({x["canonical_id"] for x in rows})!=103:
        raise ValueError("all 103 canonical rows must remain stable")
    return {**base,"records":rows,"data_version":"v37",
       "materialization_manifest":"verified_public_leads_20261028.v37.manifest.json"}

if __name__=="__main__":
    d=materialize();rows=export_records(d)
    print(json.dumps({"version":"v37","records":len(rows),
      "unique":len({x["external_id"] for x in rows}),
      "cases_with_evidence":sum(bool(x.get("mi013_source_enrichments")) for x in d["records"])},ensure_ascii=False))
