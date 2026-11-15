"""Build a separate evidence-bound business priority queue from committed archive batches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from scripts.research.import_gpb_geh_snapshots import normalize

PATTERNS = {
    "power_quality": r"\bукрм\b|\bstatcom\b|статком|компенсац.{0,30}реактив|фильтр.{0,25}гармоник|качество электроэнерг|тиристорн.{0,25}компенсатор",
    "electrical": r"электрооборудован|электроснабжен|электродвигател|трансформатор|распределительн.{0,20}устройств|\bкру\b|\bктп\b|\bрза\b|электротехник|электропривод|частотн.{0,15}преобразовател",
    "automation_instrumentation": r"\bасу\s*тп\b|\bкип(?:иа)?\b|автоматизац|газоанализатор|контроллер|расходомер|датчик|метрологи|телемеханик|измерительн",
    "engineering_epc": r"проектирован|проектн.{0,20}работ|модернизац|реконструкц|пусконалад|\bпнр\b|\bсмр\b|строительно-монтаж|\bepc\b|техническ.{0,15}перевооруж",
}
SALE = re.compile(r"^\s*(?:продажа|реализация\s+(?:имущества|неликвид|лома|отработан))",re.IGNORECASE)
WEIGHTS={"power_quality":100,"electrical":25,"automation_instrumentation":25,"engineering_epc":10}


def matches(title):
    result={}
    for key,pattern in PATTERNS.items():
        spans=[{"start":m.start(),"end":m.end(),"match":m.group()}
               for m in re.finditer(pattern,title,re.IGNORECASE)]
        if spans:
            result[key]=spans[:5]
    return result


def build(folders, db_hashes):
    candidates={}
    reviewed=Counter()
    observed=set()
    batches=[]
    for folder in folders:
        state=json.loads((folder/"state.json").read_text())
        imported=set(state.get("imported_months",[]))
        for f in sorted(folder.glob("*.result.json")):
            receipt=json.loads(f.read_text())
            sha=receipt["source_input_sha256"]
            if f.name != sha+".result.json" or receipt["replay"]["inserted"]:
                raise ValueError("unverified import result")
            months={v["month"] for v in receipt["result"]["completed_partitions"]}
            if not months <= imported:
                continue
            raw=(folder/(sha+".input.json")).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError("import input integrity mismatch")
            entries=json.loads(raw)
            if entries["schema"]!="gpb_deadline_archive_v1":
                raise ValueError("unexpected import schema")
            batches.append({"input_sha256":sha,"months":sorted(months),"rows":len(entries["accepted"])})
            for entry in entries["accepted"]:
                norm=normalize(entry);row=entry["observation"];identity=norm["external_id"]
                if db_hashes.get(identity)!=norm["content_hash"]:
                    reviewed["prior_or_changed_db_observation"]+=1
                    continue
                if identity in observed:
                    reviewed["repeated_source_identity"]+=1
                    continue
                observed.add(identity)
                if identity.startswith("sale:") or SALE.search(row["title"]):
                    reviewed["sale_excluded"]+=1
                    continue
                evidence=matches(row["title"])
                if not evidence:
                    continue
                price=norm["raw_payload"]["initial_price_decimal"]
                candidates[identity]={"external_id":identity,"title":row["title"],"entry":entry,
                    "db_content_sha256":norm["content_hash"],"input_sha256":sha,
                    "matches":evidence,"score":sum(WEIGHTS[k] for k in evidence),
                    "initial_price_rub":price,"verification":"SOURCE_BOUND_LEXICAL_CANDIDATE_NOT_AWARD"}
    ordered=sorted(candidates.values(),key=lambda r:(-r["score"],-Decimal(r["initial_price_rub"] or "0"),r["external_id"]))
    return {"schema":"geh_archive_priority_v1","verified_db_rows":len(observed),
            "candidate_count":len(ordered),"category_counts":dict(Counter(k for r in ordered for k in r["matches"])),
            "review_counts":dict(reviewed),"batches":batches,"candidates":ordered}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--imports",type=Path,nargs="+",required=True)
    p.add_argument("--db-hashes",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    obj=build(a.imports,json.loads(a.db_hashes.read_text()))
    raw=json.dumps(obj,ensure_ascii=False,indent=2).encode()
    with a.output.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({k:v for k,v in obj.items() if k not in {"batches","candidates"}},ensure_ascii=False))
    print("queue sha256",hashlib.sha256(raw).hexdigest())


if __name__=="__main__":
    main()
