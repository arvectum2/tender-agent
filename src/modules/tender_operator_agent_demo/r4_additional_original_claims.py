"""Recheck four additional official EIS procurement attachment and LLM receipts.

Evidence is pinned private data; never publish raw UID, local file path,
model quote contents, or infer legal correctness from literal text agreement.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

PINS={
    "official":"df63a7619518ad9415ce81b7b27c964e8c81724d2f50fe497f428838dcbdecaf",
    "extract":"f2ecdc6a1a8966185c4a8ec35b0b7ae03f0a01f3e4bb2b72c013d9752557b707",
    "model":"3b009ba33feb01893fe7ff017b73a8eb1e4d6a9790d24b854f12e0e08bc489df",
}
IDS={"0151600003226000011":4,"0162200011826003089":5,
     "0152200004026000069":6,"0348100024426000021":6}


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def pinned(path:Path,expected:str)->dict:
    data=path.read_bytes()
    if sha(data)!=expected:
        raise ValueError("supplementary original source receipt digest mismatch")
    return json.loads(data)


def _trusted_private_file(base:Path,path:str)->Path:
    p=Path(path)
    if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(base.resolve()):
        raise ValueError("untrusted outside or missing original EIS source file")
    return p


def audit_additional_sources(source_root:Path)->dict:
    folder=source_root/"ai-expert-20261012/positive-docs-recovery-20261012"
    rec=pinned(folder/"official-21-attachments-receipt.json",PINS["official"])
    texts=pinned(folder/"text-extraction-21-receipt.json",PINS["extract"])
    model=pinned(folder/"gemma-four-new-positive-private.json",PINS["model"])
    files=rec.get("results",[])
    if len(files)!=21 or Counter(row["reg_number"] for row in files)!=Counter(IDS):
        raise ValueError("21 additional original attachments are not complete")
    originals={}
    for file in files:
        n=file["reg_number"]
        uid=file["uid"]
        extension=file["file_extension"]
        if file["status"]!="OFFICIAL_BINARY_VERIFIED" or not uid.isalnum():
            raise ValueError("nonattested official attachment")
        expected=folder/n/(uid+extension)
        p=_trusted_private_file(folder, file["private_local_path"])
        if p!=expected or p.stat().st_size!=file["actual_bytes"] or sha(p.read_bytes())!=file["sha256"]:
            raise ValueError("original official attachment SHA/size/identity differs")
        key=(n,uid)
        if key in originals:
            raise ValueError("duplicate source attachment UID")
        originals[key]=file["sha256"]
    parsed=texts.get("text_units",[])
    if len(parsed)!=22:
        raise ValueError("unexpected original document extracted text receipts")
    source_text={}
    for item in parsed:
        key=item["reg_number"],item["source_uid"]
        if key not in originals or item["outer_sha256"]!=originals[key]:
            raise ValueError("saved extracted content linked to wrong original binary")
        path=_trusted_private_file(folder,item["private_text_path"])
        if item["text_status"]!="TEXT_EXTRACTED" or sha(path.read_bytes())!=item["text_sha256"]:
            raise ValueError("source extract missing or hash mismatch")
        combined=(*key,item["text_sha256"])
        if combined in source_text:
            raise ValueError("duplicate extracted original text locator")
        source_text[combined]=path.read_text(encoding="utf8")
    cases=model.get("results",[])
    if len(cases)!=4 or {r["reg_number"] for r in cases}!=set(IDS):
        raise ValueError("additional four model claim cases missing")
    claims=[]
    batches_over=0
    for row in cases:
        n=row["reg_number"]
        if row.get("max_claims_requested")!=3:
            raise ValueError("unexpected model claim policy request")
        count_ok=len(row.get("claims") or [])<=3
        if row["format_claim_count_ok"] is not count_ok:
            raise ValueError("model output count approval conflicts with actual claims")
        if not count_ok:
            batches_over+=1
        for i,claim in enumerate(row.get("claims",[]),1):
            key=(n,claim["source_uid"])
            tkey=(*key,claim["text_sha256"])
            if key not in originals or claim["original_sha256"]!=originals[key] or tkey not in source_text:
                raise ValueError("LLM claim points to unverified or inconsistent original attachment")
            quote=claim.get("exact_quote","")
            if not isinstance(quote,str) or not quote:
                raise ValueError("missing source quotation")
            exact=quote in source_text[tkey]
            claims.append({
                "registry_number":n,"claim_index":i,
                "original_binary_sha256":originals[key],
                "original_text_sha256":claim["text_sha256"],
                "quote_sha256":sha(quote.encode("utf8")),
                "quote_literal":exact,
                "quote_chars":len(quote),
                "quote_length_valid":18<=len(quote)<=180,
                "claim_format_count_valid":count_ok,
                "semantic_or_legal_gold_signed":False,"bid_ready":False,
            })
    if len(claims)!=21:
        raise ValueError("unexpected source claim count in four model runs")
    return {
        "source":"PINNED_PRIOR_FIRST_PARTY_EIS_2026_10_12",
        "original_binaries_sha_verified":len(originals),
        "normalized_texts_sha_verified":len(source_text),
        "four_competitive_case_count":len(cases),
        "model_claims_checked":len(claims),
        "model_claims_exact_source_quotes":sum(c["quote_literal"] for c in claims),
        "claims_requiring_quote_correction":sum(not c["quote_literal"] for c in claims),
        "claims_breaching_quote_length_policy":sum(not c["quote_length_valid"] for c in claims),
        "model_batches_exceeding_claim_count_cap":batches_over,
        "human_legal_signoffs":0,
        "claim_checks":claims,
    }
