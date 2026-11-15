"""Read-only audit of completed source-bound Moscow quotation sessions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from time import strptime


def money(value):
    v = Decimal(str(value))
    if not v.is_finite() or v <= 0:
        raise ValueError("invalid monetary value")
    return v


def stamp(value):
    return strptime(value, "%d.%m.%Y %H:%M:%S")  # Source civil order; no timezone inferred.


def audit(row, detail):
    ident = detail["id"]
    if ident != row["auctionId"] or row["stateId"] != 19000004 or detail["state"]["id"] != 19000004:
        raise ValueError("identity or state mismatch")
    start, final = money(detail["startCost"]), money(detail["lastBetCost"])
    if start != money(row["startPrice"]) or final != money(row["auctionCurrentPrice"]) or final > start:
        raise ValueError("price mismatch")
    if detail.get("contractCost") is not None or detail.get("contracts"):
        raise ValueError("contract evidence requires separate review")
    items = detail["items"]
    if not items or len({x["id"] for x in items}) != len(items):
        raise ValueError("invalid items")
    if sum(money(x["currentValue"])*money(x["costPerUnit"]) for x in items).quantize(Decimal(".01")) != start.quantize(Decimal(".01")):
        raise ValueError("initial basket differs")
    bets = sorted(detail["bets"], key=lambda x:x["num"])
    if not bets or [x["num"] for x in bets] != list(range(1,len(bets)+1)) or len({x["id"] for x in bets}) != len(bets):
        raise ValueError("invalid sequence")
    previous, t, end = start, stamp(detail["startDate"]), stamp(detail["endDate"])
    participants = set()
    for b in bets:
        p, dt = money(b["cost"]), stamp(b["serverTime"])
        if b["auctionId"] != ident or b["isBlocked"] is not False or p >= previous or not t <= dt <= end:
            raise ValueError("invalid bid sequence")
        previous, t = p, dt
        participants.add(b["supplier"]["id"])
    if previous != final or bets[-1]["id"] != detail["lastBetId"]:
        raise ValueError("final bid mismatch")
    return {"auction_id":str(ident),"initial_rub":str(start),"last_bid_rub":str(final),
            "reduction_percent":str(((start-final)/start*100).quantize(Decimal(".01"))),
            "positions":len(items),"positions_with_platform_sku_id":sum(x.get("skuId") is not None for x in items),
            "bids":len(bets),"automatic_bids":sum(x["isAutoBet"] is True for x in bets),
            "reported_participants":detail["uniqueSupplierCount"],"distinct_bid_supplier_tokens":len(participants),"participant_count_matches":len(participants)==detail["uniqueSupplierCount"],"winner_summary_matches_bid_supplier":bets[-1]["supplier"]["id"]==detail["lastBetSupplier"]["id"],"contract_amount_rub":None,"actual_profit_rub":None,
            "verification":"OBSERVED_BID_SEQUENCE_NOT_CONTRACT","execution_allowed":False}


def verified_json(path,sha):
    if not re.fullmatch("[0-9a-f]{64}",sha) or path.is_symlink():
        raise ValueError("invalid source identity")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise ValueError("source SHA mismatch")
    return json.loads(raw,parse_float=Decimal)


def run(root):
    report=json.loads((root/"mos-paper-economics-v1.json").read_text())
    if report["execution_allowed"] is not False or report["actual_cost_evidence_count"] or report["signed_contract_evidence_count"]:
        raise ValueError("unexpected report scope")
    folder=root/"mos-finished-pilot"
    results=[]
    for s in report["sessions"]:
        ident=s["trace"]["auction_id"]
        l,d=s["list_sha256"],s["detail_sha256"]
        if not ident.isdecimal() or not all(re.fullmatch("[0-9a-f]{64}",sha) for sha in (l,d)):
            raise ValueError("invalid receipt")
        page=verified_json(folder/("list-"+l+".json"),l)
        detail=verified_json(folder/("auction-"+ident+"-"+d+".json"),d)
        rows=[r for r in page["items"] if str(r["auctionId"])==ident]
        if len(rows)!=1:
            raise ValueError("missing or ambiguous list identity")
        facts=audit(rows[0],detail)
        for k,prior in (("initial_rub","observed_start_rub"),("last_bid_rub","observed_final_bid_rub"),("reduction_percent","reduction_percent")):
            if Decimal(facts[k])!=Decimal(s["trace"][prior]):
                raise ValueError("prior facts differ")
        results.append({**facts,"list_sha256":l,"detail_sha256":d})
    if len({r["auction_id"] for r in results})!=len(results):
        raise ValueError("duplicate sessions")
    return {"schema":"mos_paper_source_audit_v1","sessions":results,"session_count":len(results),
            **{k:sum(r[k] for r in results) for k in ("bids","automatic_bids","positions","positions_with_platform_sku_id")},
            "verified_time_valid_supplier_costs":0,"verified_signed_contracts":0,"execution_allowed":False}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    print(json.dumps(run(p.parse_args().root),ensure_ascii=False,indent=2))
