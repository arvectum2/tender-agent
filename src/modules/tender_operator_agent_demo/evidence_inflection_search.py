"""Conservative opt-in discovery, never source attestation or semantic answers."""
from __future__ import annotations

import re
from functools import lru_cache
from itertools import islice

from .evidence_document_search import _candidate
from .relevance_scoring import _inflection_stem

_WORDS = re.compile(r'[^\W_]{3,}')
_RUSSIAN = re.compile(r'[а-яё]+\Z')
_EXACT_WEIGHT = 32  # greater than the maximum number of query terms (16)


def _key(word: str) -> str:
    normalized = word.casefold()
    if not _RUSSIAN.fullmatch(normalized):
        return normalized
    normalized = normalized.replace('ё', 'е')
    # Long common inflection stems only. No broad prefix or synonym match.
    for suffix in ('иями','иям','иях','ией','ии'):
        if normalized.endswith(suffix) and len(normalized)-len(suffix)>=5:
            return normalized[:-len(suffix)]
    return _inflection_stem(normalized)


def inflection_candidate(text: str, terms: set[str], *, require_two: bool = False) -> tuple[int, str] | None:
    """Prioritize the existing exact candidate; otherwise search literal windows.

    Do not rewrite the returned excerpt, and bound the number of verified
    candidates using the existing search API. This does not imply relevance.
    """
    exact = _candidate(text, terms)
    if exact:
        return exact[0] * _EXACT_WEIGHT, exact[1]
    keys = {_key(t) for t in terms if _RUSSIAN.fullmatch(t)}
    if not keys:
        return None
    # Cache only token keys within this call, not text or source evidence.
    key = lru_cache(maxsize=2048)(_key)
    best = None
    for i,line in enumerate(text.splitlines()):
        if i >= 20000:
            break
        line = line.strip()
        if len(line) < 20:
            continue
        matches = (m for m in _WORDS.finditer(line) if key(m.group().casefold()) in keys)
        for m in islice(matches,24):
            excerpt=line[max(0,m.start()-60):min(len(line),m.end()+100)].strip()
            score=len({key(t.group().casefold()) for t in _WORDS.finditer(excerpt)} & keys)
            if len(excerpt)>=20 and score and (best is None or score>best[0]):
                best=score,excerpt
        if best and best[0]==len(keys):
            break
    if require_two and len(terms)>1 and (best is None or best[0]<2):
        return None
    return best


def guarded_inflection_candidate(text: str, terms: set[str]) -> tuple[int, str] | None:
    """Require two distinct term keys for new multi-term fallback hits."""
    return inflection_candidate(text, terms, require_two=True)
