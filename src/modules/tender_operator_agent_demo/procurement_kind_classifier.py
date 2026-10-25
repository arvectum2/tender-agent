"""Pure conservative procurement subject classification for Tender Agent.

This classifier is a product heuristic, not official EIS fact verification.
Missing/ambiguous texts remain generic; this module does not issue GO/NO-GO.
"""
from __future__ import annotations

import re


def infer_procurement_kind(*texts: str | None) -> str:
    raw_combined = re.sub(r"\s+", " ", " ".join(text or "" for text in texts if text)).strip()
    combined = raw_combined.lower().replace("ё", "е")
    if not combined:
        return "generic"

    if (
        "код активации" in combined
        and "техническ" in combined
        and "поддержк" in combined
        and any(marker in combined for marker in ("средств защиты информации", "программ", "лиценз"))
    ):
        return "software_support"

    software_objects = (
        r"программн(?:ое|ого|ому|ым|ом) обеспечен",
        r"программн(?:ый|ого|ому|ым|ом) (?:продукт|комплекс)",
        r"информационн(?:ая|ой|ую|ые|ых) систем",
        r"(?:^|\W)saas(?:\W|$)",
        r"(?:^|\W)пк\s*[«\"]",
    )
    has_software_object = any(re.search(pattern, combined) for pattern in software_objects) or bool(
        re.search(r"(?:^|\W)ПО(?:\W|$)", raw_combined)
    )
    has_software_change = bool(
        re.search(r"\b(?:внедрен|доработ|модификац|разработ|обновлен|сопровожден)\w*", combined)
    )
    has_software_license = bool(
        re.search(r"(?:неисключительн\w*\s+прав|прав\w*\s+(?:на|использован)|передач\w*\s+прав)", combined)
        or ("лиценз" in combined and has_software_object)
    )
    has_integration = any(
        marker in combined
        for marker in ("интеграц", "смэв", "обмен данн", "api", "межведомствен", "витрин")
    )
    embedded_hardware_software = bool(
        re.search(r"(?:оборудован|компьютер|контроллер|модул)\w*.*(?:встроенн|предустановленн|прошивк)\w*.*(?:по|программ)", combined)
        or re.search(r"(?:встроенн|предустановленн|прошивк)\w*.*(?:по|программ)\w*.*(?:оборудован|компьютер|контроллер|модул)", combined)
    )
    software_semantics = has_software_object and not embedded_hardware_software
    if software_semantics:
        if has_integration and (has_software_change or has_software_license):
            return "mixed"
        if has_software_change:
            return "software_modification"
        if has_software_license:
            return "license"
        if has_integration:
            return "integration"

    if re.search(r"лицензируем\w*\s+(?:вид|деятельност)", combined) and not has_software_object:
        return "generic"

    if "работы электромонтажные" in combined or "выполнение работ" in combined:
        return "works"
    scores = {
        "goods": sum(
            combined.count(marker)
            for marker in (
                "поставка",
                "товар",
                "оборудован",
                "поставк",
                "склад",
                "разгруз",
                "гарантия на товар",
            )
        ),
        "works": sum(
            combined.count(marker)
            for marker in (
                "выполнение работ",
                "работы",
                "результат работ",
                "этап работ",
                "акт сдачи",
                "замена",
                "монтаж",
                "демонтаж",
                "ремонт",
                "пусконалад",
                "смета",
                "кс-2",
                "кс-3",
            )
        ),
        "services": sum(
            combined.count(marker)
            for marker in (
                "оказание услуг",
                "услуг",
                "место оказания услуг",
            )
        ),
        "software_modification": sum(
            combined.count(marker)
            for marker in (
                "программн",
                "пк «",
                "пк \"",
                "программного комплекса",
                "программный комплекс",
                "программного обеспеч",
                "модификац",
                "доработ",
                "модул",
                "сэмд",
                "электронных медицинских документ",
                "исходн",
            )
        ),
        "integration": sum(
            combined.count(marker)
            for marker in (
                "интеграц",
                "смэв",
                "api",
                "витрин",
                "межведомствен",
                "обмен данн",
            )
        ) + len(re.findall(r"(?<!\w)ерн(?!\w)", combined)),
        "license": sum(
            combined.count(marker)
            for marker in (
                "лиценз",
                "права использования",
                "неисключительн",
                "передача прав",
            )
        ),
    }
    if scores["software_modification"] >= 2 and (scores["integration"] >= 1 or scores["license"] >= 1):
        return "mixed"
    if scores["software_modification"] >= 2:
        return "software_modification"
    if scores["integration"] >= 2:
        return "integration"
    if scores["license"] >= 2:
        return "license"
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    return "generic"

