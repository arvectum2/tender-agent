"""Deterministic, role-evidence-first customer identity resolution.

A customer name is returned only for explicit customer-role evidence:

1. structured customer fields (``customerName``, customer-scoped ``fullName``);
2. explicit textual customer labels (``Заказчик: <org>``, including the
   role cell merged with its value cell and the bare role label followed by
   the organization on a neighboring line);
3. explicit contract-party preambles (``<org>, именуем... «Заказчик»``).

Generic ``<fullName>`` nodes, supplier/counterparty role words and bare role
labels are never promoted on their own.  Equally strong conflicting
candidates fail closed instead of picking first/last source.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass

# Evidence kinds, strongest first.  Table/cell/adjacent-line values are the
# same explicit-label kind as the same-line "Заказчик:" form.
_STRUCTURED_CUSTOMER_FIELD = "structured_customer_field"
_EXPLICIT_CUSTOMER_LABEL = "explicit_customer_label"
_CONTRACT_PARTY_PREAMBLE = "contract_party_preamble"

# Source roles, highest authority first.  ``combined`` is only a fallback
# carrier for explicit patterns, never a dominant source.
_SOURCE_ROLE_PRIORITY = ("notice", "contract", "technical_spec", "supporting", "combined")
_SOURCE_ROLE_RANK = {role: index for index, role in enumerate(_SOURCE_ROLE_PRIORITY)}

# Counterparty role labels that must never become a customer identity.
_COUNTERPARTY_ROLES = ("поставщик", "исполнитель", "подрядчик", "арендодатель", "продавец")
_COUNTERPARTY_VALUE_RE = re.compile(
    r"^(?:" + "|".join(_COUNTERPARTY_ROLES) + r")\s*[:.\-]?\s*$",
    re.IGNORECASE,
)
# Trailing counterparty field accidentally captured on the same flattened
# line (e.g. requisites tables): strip it, keep the organization.
_COUNTERPARTY_BOUNDARY_RE = re.compile(
    r"\s+(?:" + "|".join(_COUNTERPARTY_ROLES) + r")\s*:",
)

_CUSTOMER_NAME_TAG_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?customerName\b[^>]*>([^<]+)</(?:[A-Za-z_][\w.-]*:)?customerName>",
    re.IGNORECASE,
)
_CUSTOMER_BLOCK_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?customer\b[^>]*>(.*?)</(?:[A-Za-z_][\w.-]*:)?customer>",
    re.IGNORECASE | re.DOTALL,
)
_SCOPED_NAME_TAG_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?(?:fullName|name)\b[^>]*>([^<]+)</(?:[A-Za-z_][\w.-]*:)?(?:fullName|name)>",
    re.IGNORECASE,
)
# Same-line "Заказчик: <org>".  Horizontal whitespace only: the value must
# sit on the same flattened line, never leak into the following line.
_CUSTOMER_LABEL_LINE_RE = re.compile(
    r"(?im)^\s*Заказчик\b[ \t]*[:\-][ \t]*([^\n\t]{4,240})"
)
# Table-cell merge without a colon: "Заказчик <Org ...>" on one flattened
# line.  The value must start with an uppercase letter or quote so verb
# phrases ("Заказчик обязуется ...", "Заказчик направляет ...") never match.
# Case-SENSITIVE on purpose: the inline (?i) used elsewhere would defeat the
# uppercase guard.
_CUSTOMER_ROLE_CELL_RE = re.compile(
    r"(?m)^\s*Заказчик\b[ \t]+([А-ЯA-Z«\"][^\n\t]{3,239})"
)
# Bare role label line whose organization follows on a neighboring line.
_CUSTOMER_ROLE_LINE_RE = re.compile(r"(?im)^\s*Заказчик\b[ \t]*:?[ \t]*$")
# The organization starts with an uppercase letter (never a quote: that would
# let a match begin inside a preceding counterparty clause) and never spans
# another role-assignment clause.  Role assignment has three generic surface
# forms: "именуем...", "в дальнейшем по тексту" and "далее –".  An optional
# leading place-of-signing header stays inside the capture so the locality
# strip below can remove it.
_LOCALITY_ABBR = r"р\.п\.|г\.|д\.|с\.|ул\.|пр\.|пер\.|бул\.|наб\.|пл\.|пос\.|дер\.|х\."
_ROLE_TAIL = (
    r"(?:\s*,?\s+(?i:именуем(?:ое|ая|ый|ые)?)[\s\S]{0,80}?"
    r"|\s*,?\s+(?i:в дальнейшем по тексту)[\s\S]{0,20}?"
    r"|\s+(?i:далее)\s*[–—\-:]\s*)[«\"]Заказчик[»\"]"
)
_ROLE_TEMPERED = r"(?:(?!(?i:именуем|в дальнейшем)).){2,219}?"
_CONTRACT_PARTY_RE = re.compile(
    r"((?i:" + _LOCALITY_ABBR + r")\s+)?([А-ЯA-Z]" + _ROLE_TEMPERED + r")" + _ROLE_TAIL
)


@dataclass(frozen=True)
class CustomerResolution:
    value: str
    evidence_kind: str
    source_role: str
    confidence: str


@dataclass(frozen=True)
class _Candidate:
    value: str
    evidence_kind: str
    source_role: str
    kind_rank: int
    role_rank: int


_EVIDENCE_KIND_RANK = {
    _STRUCTURED_CUSTOMER_FIELD: 0,
    _EXPLICIT_CUSTOMER_LABEL: 1,
    _CONTRACT_PARTY_PREAMBLE: 2,
}


def _clean_text(value: str | None) -> str:
    return " ".join(html.unescape(str(value or "")).split()).strip(" ,.;:—-")


def _comparison_key(value: str) -> str:
    return _clean_text(value).lower().replace("ё", "е")


def _is_counterparty_value(value: str) -> bool:
    return bool(_COUNTERPARTY_VALUE_RE.match(_clean_text(value)))


def _strip_counterparty_boundary(value: str) -> str:
    return _COUNTERPARTY_BOUNDARY_RE.split(value, maxsplit=1)[0].strip(" ,.;:")


def _accept(value: str | None, *, evidence_kind: str, source_role: str) -> _Candidate | None:
    cleaned = _strip_counterparty_boundary(_clean_text(value))
    if not cleaned or _is_counterparty_value(cleaned):
        return None
    return _Candidate(
        value=cleaned,
        evidence_kind=evidence_kind,
        source_role=source_role,
        kind_rank=_EVIDENCE_KIND_RANK[evidence_kind],
        role_rank=_SOURCE_ROLE_RANK[source_role],
    )


def _structured_candidates(text: str, source_role: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    for raw in _CUSTOMER_NAME_TAG_RE.findall(text):
        candidate = _accept(raw, evidence_kind=_STRUCTURED_CUSTOMER_FIELD, source_role=source_role)
        if candidate is not None:
            found.append(candidate)
    for block in _CUSTOMER_BLOCK_RE.findall(text):
        scoped = _SCOPED_NAME_TAG_RE.search(block)
        if scoped:
            candidate = _accept(
                scoped.group(1), evidence_kind=_STRUCTURED_CUSTOMER_FIELD, source_role=source_role
            )
            if candidate is not None:
                found.append(candidate)
    return found


def _label_candidates(text: str, source_role: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    for pattern in (_CUSTOMER_LABEL_LINE_RE, _CUSTOMER_ROLE_CELL_RE):
        for match in pattern.finditer(text):
            candidate = _accept(
                match.group(1), evidence_kind=_EXPLICIT_CUSTOMER_LABEL, source_role=source_role
            )
            if candidate is not None:
                found.append(candidate)
    return found


def _adjacent_candidates(text: str, source_role: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not _CUSTOMER_ROLE_LINE_RE.match(line):
            continue
        for following in lines[index + 1 : index + 4]:
            stripped = _clean_text(following)
            if not stripped:
                continue
            if _is_counterparty_value(stripped):
                continue
            candidate = _accept(
                stripped, evidence_kind=_EXPLICIT_CUSTOMER_LABEL, source_role=source_role
            )
            if candidate is not None:
                found.append(candidate)
            break
    return found


_ROLE_PHRASE_RE = re.compile(_ROLE_TAIL)
# A place-of-signing header ("р.п. Краснообск") glued to the organization by
# layout flattening is not part of the legal name.  Organization names do not
# begin with a locality abbreviation, so strip exactly one leading
# "<abbr> <Place>" when more organization text follows.
_LOCALITY_PREFIX_RE = re.compile(
    r"^(?:" + _LOCALITY_ABBR + r")"
    r"\s+[А-ЯA-ZЁ][^\s]*\s+(?=[А-ЯA-ZЁ«\"])",
    re.IGNORECASE,
)
# An uppercase word directly continuing "р.п. " / "г. " / ... is the place
# name of a signing header, not the start of the organization.
_PLACE_AFTER_ABBR_RE = re.compile(
    r"(?:" + _LOCALITY_ABBR + r")\s+$",
    re.IGNORECASE,
)


def _strip_leading_locality(capture: str) -> str:
    stripped = _LOCALITY_PREFIX_RE.sub("", capture, count=1).strip()
    return stripped or capture
_UPPERCASE_START_RE = re.compile(r"[А-ЯA-Z]")
# A place-of-signing header ("р.п. Краснообск") precedes the organization on
# the same flattened line.  These lowercase starts exist only so the locality
# strip below can remove them; anything else about them follows the same
# capture filters.
_LOCALITY_START_RE = re.compile(
    r"(?:р\.п\.|г\.|д\.|с\.|ул\.|пр\.|пер\.|бул\.|наб\.|пл\.|пос\.|дер\.|х\.)\b",
    re.IGNORECASE,
)
_QUOTED_SPAN_RE = re.compile(r"«[^»\n]*»|\"[^\n\"]*\"")
# A single organization name never spans a party-clause boundary.  Captures
# crossing one belong to a preceding counterparty clause, not the customer.
_PARTY_CLAUSE_MARKERS = ("с одной стороны", "с другой стороны")
# A preamble organization never starts more than this far before its role
# phrase; bounds the start enumeration below.
_PREAMBLE_WINDOW = 260
# Short dotted tokens are abbreviations/initials (г., ул., Н., А.), not
# sentence ends.  Anything else ending a sentence cannot sit inside one
# organization name.  Form-field blanks ("__") are layout, never identity.
_ABBREVIATION_RE = re.compile(r"\b[А-Яа-яA-Za-zЁё]{1,3}\.")
_SENTENCE_BREAK_RE = re.compile(r"[.!?;]|_{2,}")


def _has_sentence_break(capture: str) -> bool:
    return bool(_SENTENCE_BREAK_RE.search(_ABBREVIATION_RE.sub("", capture)))


def _preamble_candidates(text: str, source_role: str) -> list[_Candidate]:
    # Newlines inside a preamble are layout, not semantics.
    flattened = re.sub(r"\s+", " ", text)
    # Several party clauses may precede the customer clause on one flattened
    # line (supplier preamble first, customer preamble second).  The
    # organization belongs to the NEAREST role phrase, so for every role
    # phrase keep only the shortest valid capture ending at it.
    quoted = [
        (span.start(), span.end()) for span in _QUOTED_SPAN_RE.finditer(flattened)
    ]

    def _inside_quotes(position: int) -> bool:
        return any(start <= position < end for start, end in quoted)

    def _crosses_party_clause(capture: str) -> bool:
        lowered = capture.lower()
        return any(marker in lowered for marker in _PARTY_CLAUSE_MARKERS)

    # A candidate start inside a quoted span truncates a longer name instead
    # of naming the customer; other starts are judged by the capture filters
    # below (party clauses, sentence breaks, form blanks).

    # The organization name runs maximally to its own role phrase: among the
    # surviving starts, a later one merely truncates the name.  Starts inside
    # quoted spans, after sentence ends, captures crossing another role
    # clause, crossing a party-clause boundary, or spanning sentence breaks
    # and form blanks are excluded first.
    def _starts(window_start: int, role_start: int) -> list[int]:
        positions = [
            match.start()
            for match in _UPPERCASE_START_RE.finditer(flattened, window_start, role.start())
            if not _inside_quotes(match.start())
            and not _LOCALITY_PREFIX_RE.match(flattened[match.start():])
            and not _PLACE_AFTER_ABBR_RE.search(flattened[: match.start()])
        ]
        positions.extend(
            match.start()
            for match in _LOCALITY_START_RE.finditer(flattened, window_start, role.start())
        )
        return sorted(set(positions))

    best_by_role: dict[int, str] = {}
    for role in _ROLE_PHRASE_RE.finditer(flattened):
        window_start = max(0, role.start() - _PREAMBLE_WINDOW)
        for position in _starts(window_start, role.start()):
            match = _CONTRACT_PARTY_RE.match(flattened, pos=position)
            if match is not None and match.end() == role.end():
                # Group 1 is the optional place-of-signing header; group 2
                # the organization itself.
                capture = (match.group(1) or "") + match.group(2)
                if _crosses_party_clause(capture):
                    continue
                if _has_sentence_break(capture):
                    continue
                current = best_by_role.get(role.end())
                if current is None or len(capture) > len(current):
                    best_by_role[role.end()] = capture
                # NOTE: longest wins only among survivors above; exclusions
                # carry the precision (quoted spans, party markers, sentence
                # breaks, form blanks).
    found: list[_Candidate] = []
    for end in sorted(best_by_role):
        candidate = _accept(
            _strip_leading_locality(best_by_role[end]),
            evidence_kind=_CONTRACT_PARTY_PREAMBLE,
            source_role=source_role,
        )
        if candidate is not None:
            found.append(candidate)
    return found


def _collect(text: str | None, source_role: str) -> list[_Candidate]:
    if not text or not str(text).strip():
        return []
    candidates = _structured_candidates(text, source_role)
    candidates.extend(_label_candidates(text, source_role))
    candidates.extend(_adjacent_candidates(text, source_role))
    candidates.extend(_preamble_candidates(text, source_role))
    return candidates


def resolve_customer_name(
    *,
    notice_text: str | None = None,
    contract_draft_text: str | None = None,
    technical_spec_text: str | None = None,
    supporting_texts: Sequence[str | None] = (),
    combined_text: str | None = None,
) -> CustomerResolution | None:
    """Resolve the contracting customer from explicit role evidence.

    Returns the strongest explicit candidate or ``None`` when evidence is
    missing, role-only, or equally strong but conflicting.
    """

    sources: list[tuple[str, str | None]] = [
        ("notice", notice_text),
        ("contract", contract_draft_text),
        ("technical_spec", technical_spec_text),
    ]
    sources.extend(("supporting", item) for item in supporting_texts)
    sources.append(("combined", combined_text))

    candidates: list[_Candidate] = []
    for role, text in sources:
        candidates.extend(_collect(text, role))
    if not candidates:
        return None

    candidates.sort(key=lambda item: (item.kind_rank, item.role_rank))
    best = candidates[0]
    for challenger in candidates[1:]:
        if (
            challenger.kind_rank,
            challenger.role_rank,
        ) != (
            best.kind_rank,
            best.role_rank,
        ):
            break
        if _comparison_key(challenger.value) != _comparison_key(best.value):
            return None
    confidence = "high" if best.kind_rank == 0 else "medium"
    return CustomerResolution(
        value=best.value,
        evidence_kind=best.evidence_kind,
        source_role=best.source_role,
        confidence=confidence,
    )
