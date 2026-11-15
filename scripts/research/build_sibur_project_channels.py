"""Versioned project-mention evidence, source refresh and restricted role claims."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict

PROJECTS = {
    "AGHK": r"\bАГХК\b|Амурск\w+\s+(?:газохимическ\w+\s+комплекс|ГХК)",
    "AGPZ": r"\bАГПЗ\b|Амурск\w+\s+(?:газоперерабатывающ\w+\s+завод|ГПЗ)",
    "DGP2": r"\bДГП[ -]?2\b|\bPDH2\b",
    "NPG_SPR": r"\bНПГ\s*(?:&|и|/|[-–])?\s*(?:СПР|SPR)\b|\bНПГSPR\b|неопентилгликол\w*",
    "STYRENE": r"стирольн\w+\s+цепочк|этилбензол\w*\s*/\s*стирол",
    "EP600": r"\bЭП[ -]?600\b|\bEP[ -]?600\b",
    "METALLOCENE_PE": r"металлоценов\w+\s+полиэтилен",
    "ETHYLENE_PIPE": r"этиленопровод\w*",
    "NKNH_ASU": r"воздухоразделительн\w+\s+установк|\bВРУ\b",
}
BRANDS = {
    "ABB": r"\bABB\b", "Siemens": r"\bSiemens\b|\bСименс\b",
    "Schneider Electric": r"\bSchneider\b|Шнейдер",
    "Emerson/Rosemount": r"\bEmerson\b|\bRosemount\b",
    "Yokogawa": r"\bYokogawa\b|Йокогава",
    "Endress+Hauser": r"Endress\s*\+?\s*Hauser|\bE\+H\b",
    "KROHNE": r"\bKrohne\b", "WIKA": r"\bWika\b",
    "AUMA": r"\bAUMA\b", "AuCom": r"\bAuCom\b",
    "WOLONG": r"\bWolong\b", "Dräger": r"\bDr[aä]ger\b",
    "Honeywell": r"\bHoneywell\b", "VEGA": r"\bVEGA\b",
    "Danfoss": r"\bDanfoss\b", "Rockwell": r"\bRockwell\b",
}
TECH = r"тех\.?\s*проработк|техническ\w+\s+проработк|без\s+цен|предварительн\w+\s+проработк"
BUDGET = r"бюджетн\w+\s+оценк|\bБО\b|оценочн\w+\s+стоимост"


def matches(text, patterns):
    return {k:m.group(0) for k,p in patterns.items() if (m:=re.search(p,text,re.IGNORECASE))}


def build(sales, current, receipts):
    old = {x["external_id"]:x for x in sales["candidates"] if x["core_tags"]}
    records = []
    by_project = defaultdict(list)
    brand_counts = Counter()
    for ident, r in old.items():
        text = " ".join([r["title"],*r["subject"]]).replace("_"," ")
        projects = matches(text, PROJECTS)
        if "NKNH_ASU" in projects and not ("Нижнекамскнефтехим" in r["site_mentions"] or "Нижнекамскнефтехим" in r["organizer"]):
            del projects["NKNH_ASU"]
        brands = matches(text, BRANDS)
        brand_counts.update(brands.keys())
        if projects or brands:
            rec = {"external_id":ident,"organizer":r["organizer"],"title":r["title"],
                   "project_mentions":projects,"brand_mentions":brands,"source_receipts":r["source_receipts"],
                   "core_tags":r["core_tags"],"budget_signal":r["budget_signal"],
                   "signed_contract":None,"supplier":None}
            records.append(rec)
            for p in projects:
                by_project[p].append(rec)
    now = {x["external_id"]:x["observations"] for x in current}
    if len(now)!=len(current):
        raise ValueError("duplicate current identity")
    seen = []
    for old_r in sales["core_active_snapshot"]:
        ident = old_r["external_id"]
        obs = now.get(ident,[])
        status = sorted({o["status_raw"] for o in obs})
        deadline = sorted({o["deadline_raw"] for o in obs})
        text = " ".join(o["title"]+" "+o["subject"] for o in obs).replace("_"," ")
        phase = ("budget" if re.search(BUDGET,text,re.IGNORECASE) else
                 "technical_review_no_price" if re.search(TECH,text,re.IGNORECASE) else
                 "commercial_or_work_review")
        seen.append({"external_id":ident,"title":old_r["title"],"organizer":old_r["organizer"],
                     "current_list_verified":bool(obs) and receipts["advertised_pages_traversed"],
                     "status_raw":status,"deadline_raw":deadline,"phase":phase,
                     "status_deadline_unchanged":status==old_r["status_raw"] and deadline==old_r["deadline_raw"],
                     "document_urls":sorted({u for o in obs for u in o["documentation_urls"]}),
                     "source_receipts":[{k:o[k] for k in ("source_url","source_sha256","source_row")} for o in obs],
                     "verified_eligible":False})
    summary = {}
    for p, rows in by_project.items():
        summary[p] = {"publication_records":len(rows),"numeric_prefix_groups":len({r["external_id"].split("/")[0] for r in rows}),
                      "organizers":dict(Counter(r["organizer"] for r in rows)),
                      "nomenclature":dict(Counter(k for r in rows for k in r["core_tags"])),
                      "budget_signals":sum(r["budget_signal"] for r in rows)}
    return {"schema":"sibur_project_channels_v1","project_status":"MENTIONS_NOT_CONTRACT_AWARDS",
            "projects":summary,"records":records,"brand_mentions":dict(brand_counts),
            "mixed_AGHK_AGPZ_records":sum({"AGHK","AGPZ"}<=r["project_mentions"].keys() for r in records),
            "unique_project_mention_records":sum(bool(r["project_mentions"]) for r in records),
            "refresh":{k:receipts[k] for k in ("announced_pages","validated_pages","unique_ids","advertised_pages_traversed")},
            "active_review":seen}


def load(path):
    return json.loads(path.read_text())


def run(root):
    sales=root/"sales-map-v2.json"
    capture=root/"current-refresh-0953"
    receipts=load(capture/"receipts.json")
    for p in receipts["pages"]:
        raw=(capture/f"page-{p['page']:03d}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest()!=p["sha256"]:
            raise ValueError("page hash mismatch")
    report=build(load(sales),load(capture/"normalized.json"),receipts)
    report["sales_map_sha256"]=hashlib.sha256(sales.read_bytes()).hexdigest()
    report["refresh_receipts_sha256"]=hashlib.sha256((capture/"receipts.json").read_bytes()).hexdigest()
    return report
