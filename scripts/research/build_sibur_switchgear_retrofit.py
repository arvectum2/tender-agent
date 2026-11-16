"""Read-only switchgear retrofit discovery: precise terms, explicit review tiers."""
import re
from collections import Counter

CELL = r"\bКРУ[ЭМН]?\b|\bКСО\b|\bРУ[НВ]?[НВ]?\s*[-–]?\s*\d|ячейк|релейн\w+\s+отсек|выкатн\w+\s+(?:элемент|выключател)|\b(?:БАВР|РЗА|РЗиА)\b|релейн\w+\s+защит"
ACTION = r"ретрофит|retrofit|модернизац|реконструкц|замен|перевооруж|реинжиниринг"
BREAKER = r"выключател\w*|коммутационн\w+\s+аппарат"
EXPLICIT = r"ретрофит|retrofit"


def classify(title, subject):
    t = (title+" "+subject).replace("_", " ")
    if not re.search(ACTION, t, re.IGNORECASE):
        return None
    if re.search(r"\bретрофит\w*\s+(?:микропроцессорн\w+\s+блок\w*\s+SIMOREG|линий\s+выделения)", t, re.IGNORECASE):
        return "other_retrofit"
    if re.search(CELL, t, re.IGNORECASE):
        if re.search(r"ретрофит|retrofit|модернизац\w+\s+ячеек|замен\w*\s+(?:реле|РЗи?А|релейн|маслянн|вводн\w+\s+автоматическ)|микропроцессорн\w+\s+(?:терминал|устройств)",t,re.IGNORECASE):
            return "direct_switchgear_retrofit_review"
        return "related_electrical_modernization_review"
    if re.search(EXPLICIT,t,re.IGNORECASE):
        return "direct_switchgear_retrofit_review" if re.search(BREAKER,t,re.IGNORECASE) else "ambiguous_retrofit_review"
    if re.search(BREAKER,t,re.IGNORECASE):
        return "related_breaker_replacement_review"
    return None


def build(rows):
    result=[]
    for row in rows:
        obs=row["observations"]
        signal=[classify(o["title"],o["subject"]) for o in obs]
        signal=[s for s in signal if s]
        if not signal:
            continue
        result.append({"external_id":row["external_id"],"publication_date":row["publication_date"],
                       "title":row["title"],"signals":sorted(set(signal)),
                       "observations":obs,"award":None,"contract_price":None,
                       "current_eligibility_verified":False})
    return {"schema":"sibur_switchgear_retrofit_discovery_v1",
            "records":result,"count":len(result),
            "signals":dict(Counter(s for r in result for s in r["signals"])),
            "prefix_groups":len({r["external_id"].split("/")[0] for r in result})}
