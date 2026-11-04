"""Versioned, read-only field-completeness ledger for every PQ legal lot."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

DEFAULT=Path("data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261030_v2.json")
REQUIRED={
    "identity": ("id","procedure","buyer","buyer_inn","date","platform","regime","source_urls"),
    "technical": ("family","scope","description","voltage_kv","power","quantity"),
    "financial": ("nmck","bid","contract_price","equipment_only_price","paid_amount"),
    "participants": ("winner","contract_signatory","supplier_inn","epc","designer","oem"),
    "outcome": ("status","contract_no","contract_date"),
}
def evidence_grade(row):
    sources=row.get("source_urls") or []
    if any(("first_party" in s.get("tier","").lower()
            or s.get("tier","").lower().startswith("primary_"))
           and s.get("sha") for s in sources):
        return "A"
    if any(("first_party" in s.get("tier","").lower()
            or s.get("tier","").lower().startswith("primary_"))
           for s in sources):
        return "B"
    if sources:return "C"
    return "D"

def audit(corpus):
    rows=corpus["items"]
    if len(rows)!=len({r["id"] for r in rows}):
        raise ValueError("Duplicate case ID")
    case_list=[]
    coverage=collections.Counter()
    for row in rows:
        missing={}
        known={}
        for section,fields in REQUIRED.items():
            missing[section]=[f for f in fields if row.get(f) in (None,"",[],{})]
            known[section]=[f for f in fields if f not in missing[section]]
            for f in fields:
                if f in known[section]:
                    coverage[f]+=1
        if missing["identity"]:
            priority="P0/P1: identity and original source"
        elif missing["technical"]:
            priority="P2: technical specification"
        elif missing["participants"]:
            priority="P3: roles and protocol"
        elif missing["financial"] or missing["outcome"]:
            priority="P4/P5: contracts and performance"
        else:
            priority="Ready for editorial approval"
        case_list.append({
            "id":row["id"],
            "buyer":row["buyer"],
            "source_grade":evidence_grade(row),
            "review":row["review"],
            "completion_ratio":round(sum(len(x) for x in known.values())
                                     /sum(len(f) for f in REQUIRED.values()),4),
            "filled_fields":known,
            "missing_fields":missing,
            "next_priority":priority,
            "source_urls":len(row["source_urls"]),
            "signed_supplier_verified":bool(row["signed_supplier_verified"]),
            "paid_verified":bool(row["paid_verified"]),
        })
    return {
        "schema":"arvectum-pq-evidence-completeness/1",
        "snapshot_schema":corpus["schema"],
        "snapshot_date":corpus["snapshot_date"],
        "lots":len(rows),
        "fields_expected_each":sum(len(x) for x in REQUIRED.values()),
        "field_coverage":dict(sorted(coverage.items())),
        "source_grades":dict(collections.Counter(c["source_grade"] for c in case_list)),
        "cases":case_list,
        "provenance_note":"Field populated does not imply independently verified; review=unreviewed remains provisional.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,default=DEFAULT)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    d=audit(json.loads(a.snapshot.read_text(encoding="utf8")))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"lots":d["lots"],"source_grades":d["source_grades"],
       "field_coverage":d["field_coverage"]},ensure_ascii=False))
if __name__=="__main__":main()
