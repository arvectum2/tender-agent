"""Exact current-archived-notice 96-attachment provenance across EIS transports.

All four private receipt sets are SHA-pinned, all locally recovered official
attachments are rehashed. Older 72 prior downloads are attested by the
separate verified-TLS rerun; only 50 belong to these selected editions.
No live revision/legality or private file UID is exported.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from scripts.acceptance.verify_eis_filestore_receipts import verify_full_recheck

PINS={
    "old_source":"4f453e12c0013a200422990bf65a96fdfc476be6eda2b69065d18115391d9822",
    "old_verified":"96a64d6d89f48478267bb2d976b241971f140ee2939e3478b82e3aef239acb82",
    "new21":"df63a7619518ad9415ce81b7b27c964e8c81724d2f50fe497f428838dcbdecaf",
    "fresh14":"5f78318e75344020cfd9a035531178e2befbebcaefcaeee0c80a61c1c561876f",
    "fresh11":"ba641df2f40f480aa0b42166bcf6f2b429bcec31089530fa8f979478fadd2700",
}
_UID=re.compile("[A-F0-9]{32}")


def _digest(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def _load(path:Path,pin:str):
    raw=path.read_bytes()
    if len(raw)>2_000_000 or _digest(raw)!=pin:
        raise ValueError("private official source receipt digest conflicts with audit pin")
    return json.loads(raw)


def _attachments(case:dict,root:Path)->list[dict]:
    base=(root/"ai-expert-20261012/positive-eis-replacements-20261012"
          if case["role"]=="NEW_OFFICIAL_POSITIVE_REPLACEMENT"
          else root/"independent-20261012")
    z=base/case["reg_number"]/"documentation-archive.zip"
    if _digest(z.read_bytes())!=case["zip_sha256"]:
        raise ValueError("original official ZIP wrong digest")
    with zipfile.ZipFile(z) as archive:xml=archive.read(case["notice"]["xml_member"])
    if _digest(xml)!=case["notice"]["source_xml_sha256"]:
        raise ValueError("original notice document digest wrong")
    rows=[]
    for slot,node in enumerate(
        (x for x in ET.fromstring(xml).iter() if x.tag.rsplit("}",1)[-1]=="attachmentInfo"),1
    ):
        f={x.tag.rsplit("}",1)[-1]:(x.text or "") for x in node.iter()}
        parsed=urlsplit(f.get("url",""))
        query=parse_qs(parsed.query)
        uid=query.get("uid",[""])[0]
        if not (
            parsed.scheme=="https" and parsed.netloc=="zakupki.gov.ru"
            and parsed.path=="/44fz/filestore/public/1.0/download/priz/file.html"
            and len(query)==1 and len(query.get("uid",[]))==1
            and _UID.fullmatch(uid) and not parsed.fragment
        ):
            raise ValueError("wrong original EIS attachment provenance / host")
        size=int(f.get("fileSize",0))
        name=f.get("fileName","")
        if not name or not 0<size<=15_000_000:
            raise ValueError("missing source attachment filename or size")
        rows.append({"slot":slot,"uid":uid,"file_name":name,"bytes":size})
    if not rows:
        raise ValueError("original EIS notice carries no verifiable attachment inventory")
    return rows


def _local_file(root:Path,number:str,filename:str,sha:str,size:int)->None:
    if not filename or Path(filename).name!=filename or not re.fullmatch(r"\d{19}",number):
        raise ValueError("invalid local original document locator")
    doc=root/number/filename
    if not doc.is_file() or doc.is_symlink() or not doc.resolve().is_relative_to(root.resolve()):
        raise ValueError("original attachment bytes missing from saved official receipt")
    raw=doc.read_bytes()
    if len(raw)!=size or _digest(raw)!=sha:
        raise ValueError("downloaded official source bytes fail independent SHA+size check")


def verify_attachment_coverage(selection:dict,root:Path)->dict:
    independent=root/"independent-20261012"
    ai=root/"ai-expert-20261012"
    source=_load(independent/"official-filestore-72-attachment-audit.json",PINS["old_source"])
    verified=_load(independent/"bounded-filestore-verified72-private.json",PINS["old_verified"])
    proof=verify_full_recheck(source,verified,required=72)
    if proof["downloaded_binaries_recorded_verified"]!=72:
        raise ValueError("old official original verified-TLS receipt did not substantiate 72")
    newroot=ai/"positive-docs-recovery-20261012"
    new21=_load(newroot/"official-21-attachments-receipt.json",PINS["new21"])["results"]
    f14root=ai/"competitive-missing-14-originals-20261014"
    f11root=ai/"competitive-missing-11-originals-20261014"
    f14=_load(f14root/"private-originals-receipt.json",PINS["fresh14"])
    f11=_load(f11root/"private-source-receipt.json",PINS["fresh11"])
    if len(new21)!=21 or len(f14)!=14 or len(f11)!=11:
        raise ValueError("exact private source attachment receipt cardinalities incorrect")
    older={}
    for r in source["files"]:
        k=(r["reg_number"],r["official_file_uid"],r["stored_bytes"])
        if k in older:raise ValueError("duplicate original rechecked binary source")
        older[k]=r
    additional={}
    for r in new21:
        k=(r["reg_number"],r["uid"],r["actual_bytes"])
        if k in additional or r["status"]!="OFFICIAL_BINARY_VERIFIED":
            raise ValueError("new original attachment duplicates or unverified")
        _local_file(newroot,r["reg_number"],r["uid"]+r["file_extension"],r["sha256"],r["actual_bytes"])
        additional[k]=r
    fresh14={}
    for r in f14:
        k=(r["registry_number"],r["original_name"],r["declared_bytes"])
        if k in fresh14 or r["status"]!="OFFICIAL_BINARY_SHA_SAVED" or r["declared_bytes"]!=r["actual_bytes"]:
            raise ValueError("first 14 original source entries inconsistent")
        _local_file(f14root,r["registry_number"],r["private_filename"],r["sha256"],r["actual_bytes"])
        fresh14[k]=r
    fresh11={}
    for r in f11:
        k=(r["registry_number"],r["slot_in_original_notice"])
        if k in fresh11 or r["state"]!="VERIFIED_FIRST_PARTY_BINARY" or r["declared_bytes"]!=r["actual_bytes"]:
            raise ValueError("eleven recovered source entries invalid")
        _local_file(f11root,r["registry_number"],r["file"],r["sha256"],r["actual_bytes"])
        fresh11[k]=r
    cases=[]
    methods=Counter()
    used14=set()
    used11=set()
    for case in selection["positive_cases"]:
        n=case["reg_number"]
        docs=[]
        for item in _attachments(case,root):
            k=(n,item["uid"],item["bytes"])
            k14=(n,item["file_name"],item["bytes"])
            k11=(n,item["slot"])
            matches=[]
            if k in older:matches.append(("OLDER_VERIFIED_TLS_RECHECK",older[k]["stored_sha256"]))
            if k in additional:matches.append(("ADDITIONAL_ORIGINAL_DOWNLOAD",additional[k]["sha256"]))
            if k14 in fresh14:
                r=fresh14[k14]
                if Path(r["private_filename"]).stem!=f"attachment-{item['slot']:02d}" or r["original_eis_notice_xml_sha256"]!=case["notice"]["source_xml_sha256"]:
                    raise ValueError("recovered original file belongs to another archive slot/version")
                matches.append(("NEWLY_RETRIEVED_OFFICIAL_SOURCE",r["sha256"]))
                used14.add(k14)
            if k11 in fresh11:
                r=fresh11[k11]
                if r["name_in_original_notice"]!=item["file_name"] or r["declared_bytes"]!=item["bytes"] or r["notice_xml_sha256"]!=case["notice"]["source_xml_sha256"]:
                    raise ValueError("recovered original attachment does not match official notice row")
                matches.append(("NEWLY_RETRIEVED_OFFICIAL_SOURCE",r["sha256"]))
                used11.add(k11)
            if len(matches)!=1:
                raise ValueError("notice attachment lacks unique official SHA provenance")
            method,digest=matches[0]
            methods[method]+=1
            docs.append({"archive_attachment_slot":item["slot"],
                         "original_filename":item["file_name"],
                         "original_declared_bytes":item["bytes"],
                         "original_document_sha256":digest,
                         "source_proof":method,
                         "text_interpretation_approved":False})
        cases.append({"registry_number":n,"archived_version":case["notice"]["version"],
                      "required_original_attachments":len(docs),
                      "first_party_sha_verified":len(docs),
                      "documents":docs,
                      "document_content_legal_review":"NOT_APPROVED",
                      "latest_eis_revision_attested":False,"bid_ready":False})
    if len(cases)!=20 or used14!=set(fresh14) or used11!=set(fresh11):
        raise ValueError("orphan fresh official original attachments or missing positive cases")
    total=sum(c["required_original_attachments"] for c in cases)
    if total!=96 or sum(methods.values())!=total:
        raise ValueError("historical current-archived 96 attachments not covered")
    return {
        "source_scope":"20_ORIGINAL_ARCHIVED_NOTICE_VERSIONS_NOT_CURRENT_EIS",
        "case_count":20,"notice_attachment_references":total,
        "source_shas_attested":total,"evidence_methods":dict(sorted(methods.items())),
        "prior_72_TLS_verified":72,
        "fresh_20261014_binary_originals":25,
        "new_20261012_binary_originals":21,
        "human_signed_full_contract_reviews":0,
        "latest_publication_attested":False,"bid_ready":False,
        "cases":sorted(cases,key=lambda c:c["registry_number"]),
    }
