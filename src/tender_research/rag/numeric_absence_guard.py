"""Conservative exact-source numeric contradiction screen, not legal entailment."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.tender_research.rag.search_types import RagSearchHit

# Require an *explicit* absence claim for a specific field, not a generic
# uncertainty expression or another unrelated numeric field.
_ABSENT = {
    "quantity": re.compile(
        r"(?:об[ъь]ем|количеств[оа]|масса)\s+(?:товара\s+)?(?:не\s+указан[оа]?|не\s+определен[оа]?|отсутствует|неизвест[а-я]*)"
        r"|(?:не\s+указан[оа]?|не\s+определен[оа]?)\s+(?:об[ъь]ем|количеств[оа]|масса)",
        re.IGNORECASE,
    ),
    "term": re.compile(
        r"(?:срок(?:и)?|дата)\s+(?:исполнения\s+)?(?:не\s+указан[ыа]?|не\s+определен[ыа]?|неизвест[а-я]*)",
        re.IGNORECASE,
    ),
    "percent": re.compile(
        r"(?:процент|значимость\s+критерия|доля)\s+(?:не\s+указан[ао]?|не\s+определен[ао]?)",
        re.IGNORECASE,
    ),
    "price": re.compile(
        r"(?:цена|стоимость|нмцк)\s+(?:не\s+указан[ао]?|не\s+определен[ао]?|неизвест[а-я]*)",
        re.IGNORECASE,
    ),
}
_NUMBER = r"\d[\d \u00a0]*(?:[.,]\d+)?"
_EVIDENCE = {
    "quantity": re.compile(
        rf"(?:{_NUMBER})\s*(?:тонн(?:а|ы)?|т\b|кг\b|килограмм[а-я]*|литр[а-я]*|л\b|штук[а-я]*|шт\b|м3\b|единиц[а-я]*)",
        re.IGNORECASE,
    ),
    "term": re.compile(
        r"\b(?:20\d{2}[.-]\d{2}[.-]\d{2}|\d{1,2}[./]\d{1,2}[./]20\d{2})\b"
    ),
    "percent": re.compile(rf"(?:{_NUMBER})\s*%"),
    "price": re.compile(rf"(?:{_NUMBER})\s*(?:руб(?:лей|ля|ль|\.)?|₽)", re.IGNORECASE),
}


def contradicted_absence(answer: str, contexts: Sequence[RagSearchHit]) -> str | None:
    """Flag only explicit 'value absent' plus same-field directly visible value.

    False negatives are intentional; finding a numeric string cannot establish
    contractual applicability, legal effect or that the model is fully correct.
    """
    for field, denial in _ABSENT.items():
        if not denial.search(answer):
            continue
        for chunk in contexts:
            if _EVIDENCE[field].search(chunk.text):
                return field
    return None
