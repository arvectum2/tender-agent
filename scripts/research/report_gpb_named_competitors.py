"""Private, source-bound market research; never infer a contract or legal identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from scripts.research.persist_gpb_protocol_decisions import prepare
from scripts.research.triage_gpb_archive_imports import matches


def label_key(row):
    def norm(v):
        return " ".join(v.casefold().split())
    return norm(row["participant_name_as_published"]),norm(row["participant_address_as_published"])


def build(rows, tenders):
    grouped=defaultdict(list)
    for row in rows:
        if row.get("parser_schema")=="gpb_named_outcome_v4":
            grouped[row["external_id"]].append(row)
    accepted,review=[],[]
    companies=defaultdict(list)
    for ident,items in grouped.items():
        # Same procedure + same named result may have duplicate published originals.
        # Different price/name/address or tax basis requires revision review.
        facts={(label_key(r),r["best_bid_rub"],r["best_bid_tax_basis"],r["initial_price_rub"],r["initial_price_tax_basis"]) for r in items}
        if len(facts)!=1:
            review.append({"external_id":ident,"reason":"conflicting published decisions; revision unresolved","evidence":items})
            continue
        t=tenders.get(ident)
        if not t or t["source"]!="etp_gpb":
            review.append({"external_id":ident,"reason":"source identity not in verified DB","evidence":items})
            continue
        first=items[0]
        title=t["title"]
        record={"external_id":ident,"purchase_number":t["purchase_number"],"title":title,
                "customer_name":t["customer_name"],"publication_date":t["publication_date"],
                "participant_name_as_published":first["participant_name_as_published"],
                "participant_address_as_published":first["participant_address_as_published"],
                "initial_price_rub":first["initial_price_rub"],"initial_price_tax_basis":first["initial_price_tax_basis"],
                "best_bid_rub":first["best_bid_rub"],"best_bid_tax_basis":first["best_bid_tax_basis"],
                "lexical_scope_tags":list(matches(title)),"signed_contract_amount_rub":None,
                "legal_entity_inn":None,"source_evidence":items}
        accepted.append(record)
        companies[label_key(first)].append(record)
    ranks=[]
    for group in companies.values():
        sums=defaultdict(Decimal)
        for r in group:
            sums[r["best_bid_tax_basis"] or "unknown"]+=Decimal(r["best_bid_rub"])
        ranks.append({"name_as_published":group[0]["participant_name_as_published"],
                      "address_as_published":group[0]["participant_address_as_published"],
                      "selected_procedures":len(group),"best_bid_sums_by_tax_basis":{k:str(v) for k,v in sums.items()},
                      "scope_tags":dict(Counter(k for r in group for k in r["lexical_scope_tags"])),
                      "source_ids":[r["external_id"] for r in group],"verified_inn":None})
    ranks.sort(key=lambda r:(-r["selected_procedures"],-Decimal(r["best_bid_sums_by_tax_basis"].get("excludes_vat","0")),r["name_as_published"]))
    return {"schema":"gpb_named_competitor_observations_v1","verified_named_procedures":len(accepted),
            "distinct_published_name_address_pairs":len(ranks),
            "named_procedures_excludes_vat":sum(r["best_bid_tax_basis"]=="excludes_vat" for r in accepted),
            "review_count":len(review),"verified_signed_contracts":0,"companies":ranks,
            "procedures":accepted,"review":review}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--details",type=Path,nargs="+",required=True)
    p.add_argument("--tenders",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    rows=[r for folder in a.details for r in prepare(folder)]
    result=build(rows,json.loads(a.tenders.read_text()))
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode()
    with a.output.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    print("report",hashlib.sha256(raw).hexdigest(),{k:v for k,v in result.items() if k not in {"companies","procedures","review"}})
    for r in result["companies"][:10]:
        print(r["name_as_published"],r["selected_procedures"],r["best_bid_sums_by_tax_basis"],r["scope_tags"])


if __name__=="__main__":
    main()
