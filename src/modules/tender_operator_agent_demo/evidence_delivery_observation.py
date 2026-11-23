"""Literal performance term observations, not effective contractual deadlines."""
from __future__ import annotations

import re
from datetime import date
from itertools import islice
from typing import Any

_LABELS = {'services': r'сроки? оказания услуг', 'works': r'сроки? выполнения работ',
           'goods': r'сроки? поставки товара', 'contract': r'срок исполнения контракта'}
_TRIGGER = r'(?:с момента заключения контракта|с даты заключения контракта|со дня заключения контракта|с даты подписания контракта|с момента подписания контракта|с даты получения заявки заказчика)'
_DATE = r'(?P<date>[0-9]{2}\.[0-9]{2}\.[0-9]{4})(?:\s*г\.)?'
_END = re.compile(r'(?:(?P<trigger>'+_TRIGGER+r')\s+)?(?P<preposition>по|до)\s+'+_DATE+r'(?:\s*\((?P<inclusive>включительно)\))?\.?', re.IGNORECASE)
_BARE_DATE = re.compile(_DATE+r'\.?', re.IGNORECASE)
_RELATIVE = re.compile(r'в течение (?P<days>[1-9][0-9]{0,2})\s+(?P<unit>рабочих|календарных)\s+дней\s+(?P<trigger>'+_TRIGGER+r')\.?', re.IGNORECASE)


def literal_delivery_observation(quote: str, *, object_kind: str) -> dict[str, Any] | None:
    if object_kind not in _LABELS or not 20 <= len(quote) <= 800 or any(ord(c)<32 for c in quote):
        return None
    match = re.fullmatch(r'(?:\d+(?:\.\d+)*\.\s+)?'+_LABELS[object_kind]+r'\s*[:–—-]\s*(?P<body>.+)', quote, re.IGNORECASE)
    if not match:
        return None
    body = match['body']
    result = {'kind': 'LITERAL_PERFORMANCE_TERM_MENTION', 'object_kind': object_kind,
              'mentioned_date': None, 'mentioned_days': None, 'day_unit': None,
              'trigger_literal': None, 'boundary_literal': None, 'explicit_inclusive': None,
              'term_literal': body, 'effective_due_date': None,
              'trigger_sufficiency_verified': False, 'exceptions_exhaustively_checked': False}
    relative = _RELATIVE.fullmatch(body)
    if relative:
        return {**result, 'mentioned_days': int(relative['days']),
                'day_unit': 'WORKING_DAYS' if relative['unit'].casefold()=='рабочих' else 'CALENDAR_DAYS',
                'trigger_literal': relative['trigger']}
    absolute = _END.fullmatch(body)
    bare = _BARE_DATE.fullmatch(body)
    if not absolute and not bare:
        return None
    chosen = absolute or bare
    day, month, year = map(int, chosen['date'].split('.'))
    try:
        iso = date(year, month, day).isoformat()
    except ValueError:
        return None
    return {**result, 'mentioned_date': iso, 'trigger_literal': absolute['trigger'] if absolute else None,
            'boundary_literal': absolute['preposition'] if absolute else None,
            'explicit_inclusive': True if absolute and absolute['inclusive'] else None}


def delivery_candidate(text: str, _terms: set[str], *, object_kind: str) -> tuple[int, str] | None:
    """Prefer a whole extracted line; identical repeated literal terms may be sampled once."""
    selected = None
    signature = None
    for line in islice(text.splitlines(), 20000):
        quote = line.strip()
        obs = literal_delivery_observation(quote, object_kind=object_kind)
        if obs is None:
            continue
        key = obs['term_literal'].casefold()
        if selected is not None and signature != key:
            return None
        if selected is None:
            selected, signature = quote, key
    return (1, selected) if selected else None
