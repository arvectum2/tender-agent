"""Conservative saved-model quote checks against SHA-pinned original binaries.

Literal overlap with saved normalization is NOT a human endorsement of legal
interpretation. Missing source mapping fails closed, never fabricates page refs.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def index_binary_receipts(audit:dict)->dict[str,set[tuple[str,int]]]:
    items=audit.get("files")
    if not isinstance(items,list) or len(items)!=72:
        raise ValueError("original filestore receipts must contain 72 binaries")
    evidence=defaultdict(set)
    for f in items:
        key=f["reg_number"]
        proof=f["stored_sha256"],f["stored_bytes"]
        if not re.fullmatch(r"[0-9a-f]{64}",proof[0]) or not isinstance(proof[1],int) or proof[1]<=0:
            raise ValueError("invalid original file receipt")
        if proof in evidence[key]:
            raise ValueError("duplicate original binary")
        evidence[key].add(proof)
    return evidence


def verify_saved_quote(run:Path,source:str,quote:str,source_sha:str,
                       original_receipts:set[tuple[str,int]])->dict:
    if not re.fullmatch(r"file-\d{2}[-\w]*\.txt",source) or not quote.strip():
        return {"status":"UNSUPPORTED_CLAIM_LOCATOR","literal_quote":False,"original_bytes":False}
    path=run/"normalized"/source
    metadata=run/"metadata.json"
    if not path.is_file() or not metadata.is_file():
        return {"status":"SOURCE_FILE_NOT_AVAILABLE","literal_quote":False,"original_bytes":False}
    raw=path.read_bytes()
    if len(raw)>24_000_000 or sha(raw)!=source_sha:
        return {"status":"SOURCE_TEXT_SHA_MISMATCH","literal_quote":False,"original_bytes":False}
    text=raw.decode("utf8","replace")
    literal=quote in text
    file_id="-".join(source.split("-",2)[:2]).upper()
    meta=json.loads(metadata.read_text())
    matches=[f for f in meta.get("files",[]) if str(f.get("file_id","")).upper()==file_id]
    binary=False
    if len(matches)==1:
        filename=matches[0].get("stored_name")
        if isinstance(filename,str) and Path(filename).name==filename:
            attached=run/"input"/filename
            if attached.is_file() and attached.stat().st_size<=24_000_000:
                b=attached.read_bytes()
                binary=(sha(b),len(b)) in original_receipts
    status=("EXACT_QUOTE_FROM_SAVED_TEXT_WITH_OFFICIAL_BINARY_SHA" if literal and binary
            else "QUOTE_ONLY_IN_SAVED_TEXT_NOT_ORIGINAL_ATTESTED" if literal
            else "QUOTE_NOT_LITERAL_IN_PINNED_SOURCE")
    return {"status":status,"literal_quote":literal,
            "original_bytes":binary,"saved_source_sha256":sha(raw),
            "quote_sha256":sha(quote.encode("utf8")),
            "char_offset":text.find(quote) if literal else None,
            "legal_interpretation_approved":False}


def audit_claims(packet:dict,runs_root:Path,binary:dict,
                 allowed_ids:set[str])->dict:
    cases=packet.get("cases")
    if not isinstance(cases,list) or len(cases)!=10 or len({c["reg_number"] for c in cases})!=10:
        raise ValueError("independent ten-case saved expert sample incomplete")
    result=[]
    for c in cases:
        n=c["reg_number"]
        if n not in allowed_ids:
            raise ValueError("noncompetitive or foreign source in saved model claims")
        run_id=c["run_id"]
        if not re.fullmatch("toa-run-[a-z0-9-]+",run_id):
            raise ValueError("untrusted saved model run directory")
        run=runs_root/run_id
        meta=json.loads((run/"metadata.json").read_text())
        if str(meta.get("notice_number"))!=n:
            raise ValueError("saved LLM run ID points to different original procurement")
        checks=[]
        for claim in c.get("claims",[]):
            ev=claim.get("evidence",{})
            checks.append(verify_saved_quote(run,claim.get("source",""),claim.get("quote",""),
                                             ev.get("source_sha256",""),binary.get(n,set())))
        result.append({"registry_number":n,"claims":len(checks),
                       "literal_text_proven":sum(i["literal_quote"] for i in checks),
                       "literal_plus_official_original_sha":sum(i["status"]=="EXACT_QUOTE_FROM_SAVED_TEXT_WITH_OFFICIAL_BINARY_SHA" for i in checks),
                       "checks":checks,"legal_semantic_signed":False,"bid_ready":False})
    return {"saved_runs":len(result),"claims":sum(r["claims"] for r in result),
            "literal_quotes":sum(r["literal_text_proven"] for r in result),
            "literal_official_originals":sum(r["literal_plus_official_original_sha"] for r in result),
            "human_signed_legal_interpretations":0,"cases":sorted(result,key=lambda v:v["registry_number"])}
