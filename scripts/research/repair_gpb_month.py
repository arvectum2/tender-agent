"""Repair a fully captured month with repeated IDs, preserving earlier observations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

from scripts.research.capture_gpb_history_partitions import atomic, capture, inspect
from scripts.research.prepare_gpb_history_import import prepare


def audit(root, month, pages, replacement=None, replaced=frozenset()):
    ids=defaultdict(list)
    receipts=[]
    total=None
    for page in range(1,pages+1):
        folder=replacement if page in replaced else root/month
        name=f"p{page:04d}.json"
        rc=json.loads((folder/name).read_text())
        f=folder/rc["file"]
        if f.is_symlink() or f.parent!=folder:
            raise ValueError("invalid source path")
        raw=f.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=rc["sha256"]:
            raise ValueError("source SHA mismatch")
        scope=inspect(raw,month,page)
        if scope!=rc["scope"] or scope["expected_pages"]!=pages:
            raise ValueError("scope mismatch")
        if total is None:
            total=scope["reported_total"]
        if total!=scope["reported_total"]:
            raise ValueError("source count drift")
        for i in scope["ids"]:
            ids[i].append(page)
        receipts.append((folder,rc))
    if sum(map(len,ids.values()))!=total:
        raise ValueError("row count mismatch")
    return ids, receipts, total


def repair(root,month,version):
    initial=json.loads((root/"state.json").read_text())[month]
    pages=initial["expected_pages"]
    if initial["status"]!="review" or initial.get("pages")!=pages:
        raise ValueError("only fully captured review months")
    ids,_,total=audit(root,month,pages)
    affected={p for pp in ids.values() if len(pp)>1 for p in pp}
    if not 1<=len(affected)<=8:
        raise ValueError("unbounded or absent duplicate repair")
    out=root/f"repair-{month}-complete-{version}"
    replacement=out/"replacement"
    replacement.mkdir(mode=0o700,parents=True,exist_ok=True)
    for page in sorted(affected):
        capture(replacement,month,page)
    ids,receipts,total=audit(root,month,pages,replacement,affected)
    if len(ids)!=total or any(len(v)!=1 for v in ids.values()):
        raise ValueError("replacement did not close identity gap")
    dest=out/month
    dest.mkdir(mode=0o700,exist_ok=True)
    provenance=[]
    for folder,rc in receipts:
        page=rc["page"]
        for name in (f"p{page:04d}.json",rc["file"]):
            target=dest/name
            if not target.exists():
                os.link(folder/name,target)
            if target.read_bytes()!=(folder/name).read_bytes():
                raise ValueError("repair copy differs")
        provenance.append({"page":page,"source_folder":str(folder),"sha256":rc["sha256"],
                           "observed_at":rc["observed_at"]})
    atomic(out/"provenance.json",provenance)
    atomic(out/"state.json",{month:{"status":"verified_complete","source_count":total,
        "expected_pages":pages,"exposed_pages":pages,"pages":pages,"unique_ids":total,"rows":total,
        "replaced_pages":sorted(affected),"capture_version":"audited_mixed_capture"}})
    report=prepare(out,[month])
    print("repair",month,"replaced",sorted(affected),"unique",total,
          "accepted",len(report["accepted"]),"review",len(report["review"]),flush=True)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--month",required=True)
    p.add_argument("--version",choices=["v1","v2"],default="v1")
    a=p.parse_args();os.umask(0o077)
    if not a.month[:4].isdigit() or len(a.month)!=7 or a.month[4]!="-" or not a.month[5:].isdigit():
        raise ValueError("invalid month")
    repair(a.root,a.month,a.version)


if __name__=="__main__":
    main()
