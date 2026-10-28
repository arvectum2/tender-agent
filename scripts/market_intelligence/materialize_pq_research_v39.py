"""Replay all 104 MI-013 original notices with first-party signed contract winner v39."""
import copy,json
from materialize_pq_research_v38 import materialize as v38
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    base=v38()
    rows=copy.deepcopy(base["records"])
    name="original_reto_2026_competition_winner_20261028.v39.json"
    doc=json.loads((DATA/name).read_text(encoding="utf8"))
    if doc["new_procurement_notices"]!=0 or doc["existing_cases_enriched"]!=1 or len(doc["patches"])!=1:
        raise ValueError("one existing signed procurement source patch")
    patch=doc["patches"][0]
    matches=[r for r in rows if r["canonical_id"]==patch["canonical_id"]]
    if len(matches)!=1 or "v39" in matches[0].get("mi013_source_enrichments",{}):
        raise ValueError("case missing or v39 source already included")
    if not matches[0]["registered_signed_contract_verified"] or matches[0]["supplier_inn"] is not None:
        raise ValueError("cannot change named supplier on redacted signed registry")
    matches[0].setdefault("mi013_source_enrichments",{})["v39"]={
        "source_file":name,
        "verified_primary":copy.deepcopy(patch),
        "source_grade":"first_party_original_ETP_signed_final_protocol_PDF"}
    if len(rows)!=104 or len({r["canonical_id"] for r in rows})!=104:
        raise ValueError("original source count drift")
    return {**base,"records":rows,"data_version":"v39",
        "materialization_manifest":"verified_public_leads_20261028.v39.manifest.json"}

if __name__=="__main__":
    out=export_records(materialize())
    print(json.dumps({"rows":len(out),"unique":len({r["external_id"] for r in out})},ensure_ascii=False))
