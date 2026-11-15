"""Offline project package evidence, with shared documents kept distinct from scopes."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from scripts.research.technical_document_evidence import bounded, office_parts

PATTERNS = {
    "electrical_scope": r"\b(?:КРУЭ?|КТП|РУНН|РУВН|НКУ|РЗА|ИБП|УПП|ЧРП|АСДКЭ|E-SCADA)\b|трансформатор\w*|электропривод\w*|электромонтаж\w*|распределительн\w+\s+(?:шкаф|щит|устройств)",
    "automation_scope": r"\b(?:АСУ\s*ТП|КИПиА|КИП|ПЛК|SCADA|ПАЗ|РСУ)\b|расходомер\w*|газоанализатор\w*|контроллер\w*|датчик\w*",
    "technical_positions": r"\b(?:SKP23062|NKNH21002|PDH2)[-\w.]{4,70}|\b\d{4}-[A-Z]{1,5}-[A-Z0-9-]{2,24}\b",
    "voltage_power": r"\b\d+(?:[,.]\d+)?\s*(?:кВ|МВт|МВА|кВА)\b",
    "project_role": r"генеральн\w+\s+(?:подрядчик|проектировщик)|проектировщик\w*|организаци\w+\s*,?\s*выполнивш\w*|(?:заказчик|подрядчик|разработчик)\s*[:–—-]",
    "commissioning": r"\b(?:ППНР|ПНР)\b|пуско[- ]?наладочн\w*",
    "qualification": r"квалификационн\w+\s+требован|опыт\w*\s+(?:выполнен|работ)|членств\w*\s+в\s+СРО|аналогичн\w+\s+(?:договор|работ)",
}
PROJECTS = {"NPG_SPR", "STYRENE", "AGHK"}
TIERS = {"expanded_electrical_candidate", "project_package_review"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def evidence(text):
    result = {}
    for key, pattern in PATTERNS.items():
        hits = []
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start,end = max(0,m.start()-100),min(len(text),m.end()+150)
            if key == "electrical_scope" and m.group().upper() == "КРУ" and re.search(r"казначейств|счетная\s+палата|бюджетн\w+\s+контрол",text[max(0,m.start()-100):m.start()], re.IGNORECASE):
                continue
            hits.append({"start":start,"end":end,"excerpt":text[start:end]})
            if len(hits)>=8:
                break
        if hits:
            result[key] = hits
    return result


def document_parts(path, raw):
    ext = path.suffix.lower()
    if ext in {".docx",".xlsx",".pptx",".xlsm"}:
        # XML only; XLSM VBA is never executed or extracted.
        yield from office_parts(raw, ".xlsx" if ext==".xlsm" else ext)
    elif ext==".pdf":
        if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-4096:]:
            raise ValueError("invalid PDF")
        out=subprocess.run(["/opt/homebrew/bin/pdftotext","-layout",str(path),"-"],capture_output=True,timeout=15,check=True)
        yield "pdf_text_layout", bounded(out.stdout.decode("utf8"))
    else:
        raise ValueError("legacy or unsupported format")


def run(root, *, remaining=False):
    p=root/"sibur-sales-map-20261115"
    matrix=p/"whole-corpus-project-sales-matrix-v1.json"
    snapshot=p/"db-observation-snapshot-v1.json"
    m=read(matrix)
    if sha(snapshot.read_bytes())!=m["snapshot_sha256"]:
        raise ValueError("matrix snapshot mismatch")
    src={x["external_id"]:x["observations"] for x in read(snapshot)}
    cases={r["external_id"]:r for r in m["records"] if r["tier"] in TIERS and bool(PROJECTS & r["project_mentions"].keys()) != remaining}
    captures=defaultdict(list)
    all_refs=defaultdict(set)
    for folder in [root/"documents",root/"sibur-archive-discovery/categories/documents"]:
        for f in folder.glob("*.json"):
            if len(f.stem)!=64:
                continue
            r=read(f)
            if r.get("status")!="captured":
                continue
            captures[r["url"]].append((folder,f,r))
            all_refs[r["sha256"]].update(v["external_id"] for v in r["references"])
    docs={}
    missing=set()
    covered=set()
    verified_urls=set()
    for ident in sorted(cases):
        for o in src[ident]:
            ref={"external_id":ident,**{k:o[k] for k in ("source_sha256","source_row","source_url")}}
            for url in o["documentation_urls"]:
                matched=[(folder,f,r) for folder,f,r in captures.get(url,[]) if ref in r["references"]]
                if not matched:
                    missing.add((ident,url))
                    continue
                if len({r["sha256"] for _,_,r in matched})!=1:
                    raise ValueError("conflicting original")
                folder,f,r=matched[0]
                path=folder/r["file"]
                if path.is_symlink() or path.parent!=folder or path.stat().st_size>25*1024**2:
                    raise ValueError("original bounds")
                h=r["sha256"]
                if h not in docs:
                    raw=path.read_bytes()
                    if sha(raw)!=h:
                        raise ValueError("original hash mismatch")
                    parts=[]
                    error=None
                    try:
                        for part,t in document_parts(path,raw):
                            parts.append({"part":part,"text_sha256":sha(t.encode()),"chars":len(t),"matches":evidence(t)})
                    except (ValueError,KeyError,ET.ParseError,BadZipFile,subprocess.SubprocessError) as exc:
                        error=type(exc).__name__+": "+str(exc)[:150]
                    docs[h]={"original_sha256":h,"format":path.suffix,"parts":parts,
                             "error":error,"all_known_procedures":len(all_refs[h]),"references":[]}
                docs[h]["references"].append({"url":url,"capture_sha256":sha(f.read_bytes()),**ref})
                covered.add(ident)
                verified_urls.add(url)
    counts=Counter("review" if x["error"] else "extracted" if any(t["chars"] for t in x["parts"]) else "empty" for x in docs.values())
    return {"schema":"sibur_project_document_review_v1","matrix_sha256":sha(matrix.read_bytes()),
            "candidate_procedures":len(cases),"covered_procedures":len(covered),
            "verified_urls":len(verified_urls),"missing_identity_url_pairs":len(missing),
            "unique_originals":len(docs),"statuses":dict(counts),
            "shared_originals":sum(x["all_known_procedures"]>1 for x in docs.values()),
            "documents":list(docs.values()),"verification":"SOURCE_BOUND_LEXICAL_REVIEW_NOT_CONFIRMED_SCOPE_OR_AWARD"}
