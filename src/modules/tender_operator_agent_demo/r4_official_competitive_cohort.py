"""Fail-closed original EIS 20+4 cohort and XML source verification."""
from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

METHODS={
    "epNotificationEF2020":"COMPETITIVE_ELECTRONIC_AUCTION",
    "epNotificationEZK2020":"COMPETITIVE_ELECTRONIC_QUOTATIONS",
    "epNotificationEOK2020":"COMPETITIVE_OPEN_ELECTRONIC_COMPETITION",
}
PRICE_IDS={"0148300050426000047","0318200087026000163","0348100024426000052"}


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def validate_cohort(selection:dict)->dict:
    pos=selection.get("positive_cases")
    neg=selection.get("negative_cases")
    if not isinstance(pos,list) or len(pos)!=20 or not isinstance(neg,list) or len(neg)!=4:
        raise ValueError("expected 20 positive competitive and 4 negative controls")
    rows=[*pos,*neg]
    ids=[r.get("reg_number") for r in rows]
    if len(set(ids))!=24 or any(not isinstance(x,str) or not re.fullmatch(r"\d{19}",x) for x in ids):
        raise ValueError("duplicate/malformed original procurement number")
    if Counter(r.get("role") for r in pos)!={"ORIGINAL_20_CORPUS":16,"NEW_OFFICIAL_POSITIVE_REPLACEMENT":4}:
        raise ValueError("expected 16 original + 4 additional official competitors")
    methods=Counter()
    for r in pos:
        n=r.get("notice") or {}
        if METHODS.get(n.get("type_xml"))!=n.get("method"):
            raise ValueError("not a verified competitive notice type")
        if r.get("full_legal_gold_approved") is not False or r.get("owner_go")!="DEFER":
            raise ValueError("human review must never be inferred")
        methods[n["method"]]+=1
    if methods!=Counter({"COMPETITIVE_ELECTRONIC_AUCTION":11,"COMPETITIVE_ELECTRONIC_QUOTATIONS":7,
                         "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION":2}):
        raise ValueError("official competition method counts inconsistent")
    if {r["reg_number"] for r in neg if r.get("noncompetitive_reason")=="MARKET_RESEARCH_PRICE_INFORMATION_REQUEST"}!=PRICE_IDS:
        raise ValueError("three price enquiries must remain noncompetitive")
    single=[r for r in neg if r.get("noncompetitive_reason")=="SPECIAL_SINGLE_SUPPLIER_NOT_REGULAR_COMPETITIVE_TENDER"]
    if len(single)!=1 or single[0]["reg_number"]!="0349500000226000003" or single[0]["notice"]["type_xml"]!="epNotificationEZT2020":
        raise ValueError("article 93 special single-supplier original must remain negative")
    reserve=selection.get("reserve_case",{})
    if reserve.get("reg_number") in ids or reserve.get("notice",{}).get("type_xml") not in METHODS:
        raise ValueError("reserve original not separately attested")
    return {"competitive":20,"negative":4,"original_competitive":16,
            "new_original_competitive":4,"methods":dict(sorted(methods.items()))}


def verify_original_notice(case:dict,zip_path:Path)->dict:
    if not zip_path.is_file() or digest(zip_path.read_bytes())!=case.get("zip_sha256"):
        raise ValueError("original EIS ZIP bytes SHA mismatch")
    selected=case["notice"]
    with zipfile.ZipFile(zip_path) as archive:
        infos=archive.infolist()
        names=[r.filename for r in infos]
        if len(set(names))!=len(names) or any(
            i.is_dir() or i.file_size>24_000_000 or i.filename.startswith("/")
            or ".." in Path(i.filename).parts for i in infos
        ):
            raise ValueError("unsafe/ambiguous original EIS ZIP")
        if selected["xml_member"] not in names:
            raise ValueError("original notice member not found")
        raw=archive.read(selected["xml_member"])
        if digest(raw)!=selected["source_xml_sha256"]:
            raise ValueError("original notice XML SHA mismatch")
        root=ElementTree.fromstring(raw)
        xml_type=root.tag.rsplit("}",1)[-1]
        if xml_type!=selected["type_xml"]:
            raise ValueError("original XML root type conflict")
        return {
            "registry_number":case["reg_number"],
            "notice_type":xml_type,"method":selected["method"],
            "original_xml_sha256":digest(raw),"original_zip_sha256":case["zip_sha256"],
            "archived_version":selected["version"],
            "archived_submission_end":selected.get("archived_submission_endDT"),
            "original_purchase_object":selected.get("source_purchase_object"),
            "archive_xml_files":sum(str(n).lower().endswith(".xml") for n in names),
            "current_eis_attested":False,"legal_gold_signed":False,"bid_ready":False,
        }
