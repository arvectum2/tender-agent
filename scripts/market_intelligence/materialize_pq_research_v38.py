"""Replay 104 MI-013 procurements through signed original v38."""
import copy,json
from materialize_pq_research_v37 import materialize as old
from import_pq_postgres_v29 import DATA
from export_pq_data_platform import export_records

def materialize():
    base=old()
    a=copy.deepcopy(base["records"])
    d=json.loads((DATA/"original_signed_12kv_reto_20261028.v38.json").read_text(encoding="utf8"))
    if d["new_original_registered_signed_contracts"]!=1 or len(d["records"])!=1:raise ValueError("one signed registry source")
    r=copy.deepcopy(d["records"][0])
    if r["canonical_id"]!="223fz:32616181358:lot1" or not r["registered_signed_contract_verified"]:raise ValueError("source key drift")
    if r["canonical_id"] in {x["canonical_id"] for x in a}:raise ValueError("duplicate notice")
    a.append(r)
    if len(a)!=104:raise ValueError("incorrect size")
    summary=copy.deepcopy(base["verification_summary"])
    summary["total_lot_level_records"]=104
    summary["original_first_party_registered_signed_contracts"]=6
    return {**base,"records":a,"data_version":"v38","verification_summary":summary}

if __name__=="__main__":
    a=export_records(materialize())
    print(json.dumps({"records":len(a),"unique":len({x["external_id"] for x in a})}))
