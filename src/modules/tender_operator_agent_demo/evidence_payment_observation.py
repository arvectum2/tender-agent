"""Literal duration observations, never an effective contractual due date."""
from __future__ import annotations

import re
from itertools import islice
from typing import Any

# Bounded grammar: explicit digits, optional matching Russian numeral, explicit day type.
_DURATION = re.compile(r'\bв течение ([1-9][0-9]{0,2})(?:[ \t]*\(([а-яё]+)\))?[ \t]+(рабочих|календарных)\s+(?:дней|дня|день)\b', re.IGNORECASE)
_ANY_DURATION = re.compile(r'\b(?:день|дня|дней|суток|месяц\w*|недел\w*)\b', re.IGNORECASE)
_START = re.compile(r'^(?:\d+(?:\.\d+)*\.\s+)?Оплата\b', re.IGNORECASE)
_TRIGGER = re.compile(r'^\s+(?:с даты|со дня|с момента|после)\s+\S', re.IGNORECASE)
_NUMERAL = {'одного': 1, 'двух': 2, 'трех': 3, 'трёх': 3, 'четырех': 4, 'четырёх': 4,
            'пяти': 5, 'шести': 6, 'семи': 7, 'восьми': 8, 'девяти': 9, 'десяти': 10,
            'пятнадцати': 15, 'двадцати': 20, 'тридцати': 30}


def literal_payment_observation(quote: str) -> dict[str, Any] | None:
    """Recognize a single duration mention with the entire extracted line retained.

    The remaining context is verbatim and may contain conditions, cross-references,
    exclusions and further obligations. It is NOT parsed as a sufficient trigger.
    """
    if not 20 <= len(quote) <= 800 or not _START.match(quote) or not quote.endswith('.') or '\n' in quote:
        return None
    matches = list(_DURATION.finditer(quote))
    if len(matches) != 1:
        return None
    match = matches[0]
    if _ANY_DURATION.search(quote[:match.start()]) or _ANY_DURATION.search(re.sub(r'^\s+со дня\b', '', quote[match.end():], flags=re.IGNORECASE)):
        return None
    days = int(match[1])
    if match[2] is not None and _NUMERAL.get(match[2].casefold()) != days:
        return None
    before, after = quote[:match.start()], quote[match.end():]
    if re.search(r'\b(?:не|кроме|либо|или|исключая|если|при условии)\b', before, re.IGNORECASE) or not _TRIGGER.match(after):
        return None
    return {'kind': 'LITERAL_PAYMENT_DURATION_MENTION', 'mentioned_days': days,
            'day_unit': 'WORKING_DAYS' if match[3].casefold() == 'рабочих' else 'CALENDAR_DAYS',
            'duration_literal': match[0], 'following_context_literal': after.strip(),
            'effective_due_date': None, 'trigger_sufficiency_verified': False,
            'exceptions_exhaustively_checked': False, 'requires_human_review': True}


def payment_candidate(text: str, _terms: set[str], *, object_kind: str | None = None) -> tuple[int, str] | None:
    """Select a whole line, not a clipped lexical window; reject local ambiguity."""
    matches = []
    for line in islice(text.splitlines(), 20000):
        quote = line.strip()
        observation = literal_payment_observation(quote)
        if observation is None:
            continue
        if object_kind:
            before = quote[:_DURATION.search(quote).start()]
            requested, other = (r'работ\w*', r'услуг\w*') if object_kind == 'works' else (r'услуг\w*', r'работ\w*')
            if not re.search(r'\b' + requested + r'\b', before, re.IGNORECASE) or re.search(r'\b' + other + r'\b', before, re.IGNORECASE):
                continue
        if observation is not None:
            matches.append(quote)
            if len(matches) > 1:
                return None
    return (1, matches[0]) if matches else None
