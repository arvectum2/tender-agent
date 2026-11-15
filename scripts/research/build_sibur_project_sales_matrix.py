"""Whole-corpus explicit project mentions and expanded commercial scope signals.

Preserve mixed projects and unknown roles. Counts are publications, not contracts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.research.build_sibur_project_channels import PROJECTS, matches

PATTERNS = PROJECTS | {
    "NPG_SPR": r"\b(?:НПГ|NPG|NGP)\s*(?:&|и|/|[-–])?\s*(?:СПР|SPR)\b|\bНПГSPR\b|неопентилгликол\w*|\bSKP23062\b",
    "STYRENE": r"стирольн\w+\s+цепочк|этилбензол\w*\s*/\s*стирол|\bNKNH21002\b",
    "METALLOCENE_PE": r"металлоценов\w*\s*полиэтилен|\bмПЭ[- ]?300\b",
    "KOS_CATALYST": r"металлоценов\w+\s+катализатор|катализаторн\w+\s+фабрик",
    "KOS_WATER": r"узл\w*\s+нейтрализац\w*[\s,]+усреднен\w*\s+и\s+откачк\w*|\bНиОПСВ\b",
}
EXPANDED = {
    "Распределительные шкафы и щиты": r"распределительн\w+\s+шкаф|щит\w*\s+освещен|панел\w*\s+освещен",
    "Электромонтаж и электроснабжение": r"электромонтаж\w*|\bЭМР\b|электрооборудован\w*",
    "Пусконаладочные работы": r"\b(?:ППНР|ПНР)\b|пуско[- ]?налад\w*",
    "Автоматика контроля электроэнергии": r"\b(?:АСДКЭ|E-SCADA)\b|контрол\w*\s+качеств\w*\s+электроэнерг",
    "Комплексные технологические пакеты": r"блочно[- ]модульн\w+\s+комплектн\w+\s+установ|комплекс\w*\s+работ\w*",
}
TECH = r"техническ\w+\s+(?:оценк|проработк)|тех\.?\s*проработк|без\s+цен"
BUDGET = r"бюджетн\w+\s+оценк|оценк\w*\s+бюджет|\bБО\b"
DESIGN = r"проектирован\w*|рабоч\w+\s+документац|проектн\w+\s+документац|\b(?:ПИР|РД|FEED)\b"
SERVICE = r"капитальн\w+\s+ремонт|техническ\w+\s+обслуживан|ремонт\w*|диагностик\w*|модернизац\w*|тех(?:ническ\w+|\.)?\s*перевооруж"
SUPPLY = r"поставк\w*|закупк\w*|опросн\w+\s+лист|форма\s+ТКП"
CONSTRUCTION = r"\bСМР\b|строительно[- ]монтаж\w*|возведен\w*|генеральн\w+\s+подрядчик"


def build(snapshot, sales):
    core = {r["external_id"]: r for r in sales["candidates"] if r["core_tags"]}
    result = []
    for row in snapshot:
        ident = row["external_id"]
        obs = row["observations"]
        text = "\n".join(sorted({o["title"]+" "+o["subject"] for o in obs})).replace("_"," ")
        org = sorted({o["organizer"] for o in obs})
        project = matches(text, PATTERNS)
        # Generic ВРУ and НиОПСВ need a relevant site context. No promotion based
        # on ambiguous abbreviations alone. Two-project packages remain mixed.
        if "NKNH_VRU" in project and not re.search(r"Нижнекамскнефтехим|\bНКНХ\b"," ".join(org)+" "+text,re.IGNORECASE):
            del project["NKNH_VRU"]
        if "KOS_WATER" in project and not re.search(r"Казаньоргсинтез|\bКОС\b"," ".join(org)+" "+text,re.IGNORECASE):
            del project["KOS_WATER"]
        if not project:
            continue
        scope = matches(text,EXPANDED)
        old = core.get(ident)
        stages = matches(text,{"design":DESIGN,"supply":SUPPLY,"construction":CONSTRUCTION,
                               "commissioning":EXPANDED["Пусконаладочные работы"],"service_retrofit":SERVICE})
        # Explicit technical assessment after a prior budget is not a new paid order.
        phase = ("technical_assessment" if re.search(TECH,text,re.IGNORECASE) else
                 "budget_estimate" if re.search(BUDGET,text,re.IGNORECASE) else "other_publication")
        # A generic turnkey package alone is not a direct electrical scope claim.
        direct_expanded = bool(set(scope)-{"Комплексные технологические пакеты","Пусконаладочные работы"})
        tier = ("prior_core" if old else "expanded_electrical_candidate" if direct_expanded else
                "project_package_review" if scope or stages else "other_project_context")
        result.append({"external_id":ident,"title":row["title"],"organizers":org,
                       "publication_date":row["publication_date"],"project_mentions":project,
                       "scope_signals":scope,"core_tags":old["core_tags"] if old else [],
                       "work_signals":stages,"phase":phase,"tier":tier,
                       "status":sorted({o["status_raw"] for o in obs}),
                       "subjects":sorted({o["subject"] for o in obs}),
                       "source_receipts":[{k:o[k] for k in ("source_url","source_sha256","source_row")} for o in obs],
                       "contract":None,"supplier":None})
    grouped=defaultdict(list)
    for r in result:
        for p in r["project_mentions"]:
            grouped[p].append(r)
    summary={}
    for p,rows in grouped.items():
        summary[p]={"publications":len(rows),"prefix_groups":len({r["external_id"].split("/")[0] for r in rows}),
                    "tiers":dict(Counter(r["tier"] for r in rows)),
                    "phases":dict(Counter(r["phase"] for r in rows)),
                    "work_signals":dict(Counter(k for r in rows for k in r["work_signals"])),
                    "organizers":dict(Counter(k for r in rows for k in r["organizers"])),
                    "mixed_project_records":sum(len(r["project_mentions"])>1 for r in rows)}
    return {"schema":"sibur_whole_corpus_project_sales_matrix_v1","summary":summary,
            "unique_project_publications":len(result),"tiers":dict(Counter(r["tier"] for r in result)),
            "records":result,"verification":"EXPLICIT_PROJECT_MENTIONS_AND_LEXICAL_SCOPE_NOT_AWARD"}


def run(root: Path):
    snap=root/"db-observation-snapshot-v1.json"
    sales=root/"sales-map-v2.json"
    raw=snap.read_bytes()
    mapped=json.loads(sales.read_bytes())
    if hashlib.sha256(raw).hexdigest()!=mapped["snapshot_sha256"]:
        raise ValueError("source snapshot mismatch")
    report=build(json.loads(raw),mapped)
    report["snapshot_sha256"]=mapped["snapshot_sha256"]
    report["sales_map_sha256"]=hashlib.sha256(sales.read_bytes()).hexdigest()
    return report
