"""MI-013 canonical source replay v35: v34 102 plus 2023 indexed Tender.Pro original."""
import copy,json
from materialize_pq_research_v34 import materialize as v34
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    old=v34()
    arr=copy.deepcopy(old["records"])
    d=json.loads((DATA/"original_indexed_tenderpro_rmc_statcom_20261027.v35.json").read_text(encoding="utf-8"))
    if d["original_notice_count_added"]!=1 or len(d["records"])!=1:
        raise ValueError("v35 one new original-indexed notice required")
    r=copy.deepcopy(d["records"][0])
    if r["canonical_id"]!="commercial:834269:lot1" or r["equipment"]["nominal_voltage_kv"] is not None:
        raise ValueError("wrong v35 equipment source or unverified device voltage")
    if r["commission_winner"] is not None or r["actual_signed_contract_price_rub"] is not None:
        raise ValueError("do not create unsupported original awarded contract")
    if any(x["canonical_id"]==r["canonical_id"] for x in arr):
        raise ValueError("duplicate 834269 source")
    arr.append(r)
    if len(arr)!=103 or len({x["canonical_id"] for x in arr})!=103:
        raise ValueError("103 independent original notice keys expected")
    return {**old,"records":arr,"data_version":"v35","materialization_manifest":"verified_public_leads_20261027.v35.manifest.json"}

if __name__=="__main__":
    d=materialize()
    a=export_records(d)
    print(json.dumps({"version":"v35","records":len(a),"unique":len({x["external_id"] for x in a}),"source_enriched":sum(bool(x.get("mi013_source_enrichments")) for x in d["records"])},ensure_ascii=False,sort_keys=True))
