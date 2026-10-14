"""Deterministic, provenance-labeled tender excerpts for bounded LLM context.

This product-specific prioritization consumes text already extracted by the
Data Platform. It does not duplicate OCR, determine source-verified facts,
or make claims that an excerpt alone constitutes sufficient legal evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

_TERMS_BY_ROLE = {
    "notice": (
        "purchaseobjectinfo", "maxprice", "enddt", "нмцк", "извещен",
        "срок", "подач", "заявк", "предмет", "аукцион", "цена",
    ),
    "technical_spec": (
        "техническ", "требован", "срок", "этап", "результат", "приемк",
        "передач", "исходник", "доступ", "безопасн", "сайт", "фирменн",
    ),
    "contract_draft": (
        "штраф", "неустойк", "ответствен", "приемк", "оплат", "аванс",
        "обеспечен", "расторж", "срок", "гарант", "персональн", "акт",
    ),
}


# Distinct material obligations must compete for scarce excerpt windows.
# Without coverage-aware ranking several windows mentioning generic deadlines
# can crowd out accessibility, ticketing or assignment of exclusive rights.
# These are discovery cues, not evidence validation or an exhaustive checklist.
_DECISION_CRITICAL_CONCEPTS = {
    "notice": (
        ("enddt", "окончание подачи"), ("maxprice", "начальная цена"),
        ("purchasenumber", "номер закупки"),
    ),
    "technical_spec": (
        ("продажа билетов", "билет"),
        ("версия сайта для слабовидящих", "слабовид", "ограниченными возможностями зрения"),
        ("не менее 3", "не менее трех"),
        ("лично на территории", "очное интервью"),
        ("12 (двенадцать) месяцев", "гарантийный срок"),
    ),
    "contract_draft": (
        ("исключительные права", "исключительных прав"),
        ("обеспечение исполнения",),
        ("7 (семи) рабочих дней", "срок оплаты"),
        ("неустойк", "штраф"),
        ("расторжен",),
    ),
}


@dataclass(frozen=True)
class SourceExcerpt:
    role: str
    char_start: int
    char_end: int
    text: str

    @property
    def ref(self) -> str:
        return f"normalized:{self.role}:{self.char_start}-{self.char_end}"


@dataclass(frozen=True)
class DocumentContext:
    text: str
    excerpts: tuple[SourceExcerpt, ...]
    truncated: bool


def select_document_context(
    source_text: str,
    *,
    role: str,
    max_chars: int = 11500,
    window_chars: int = 1450,
) -> DocumentContext:
    """Sample whole long document, not solely its first N characters.

    Source offsets are on the normalized extracted text (not original PDF
    page numbers). For short sources the exact old text is passed unchanged.
    Long sources favor procurement/contract terms while retaining beginning
    and ending windows to reduce systematic omission of late annexes.
    """
    if max_chars < 2 * window_chars or window_chars < 250:
        raise ValueError("document excerpt budget too small")
    text = source_text or ""
    if len(text) <= max_chars:
        return DocumentContext(text=text, excerpts=(SourceExcerpt(role, 0, len(text), text),), truncated=False)

    # Nonoverlapping source windows keep offsets unambiguous, auditable and
    # prevent repeating the same clause multiple times in the model prompt.
    spans = [(i, min(i + window_chars, len(text))) for i in range(0, len(text), window_chars)]
    terms = _TERMS_BY_ROLE.get(role, ("срок", "требован", "оплат", "результат"))
    critical = _DECISION_CRITICAL_CONCEPTS.get(role, ())
    samples = [text[a:b].lower() for a, b in spans]

    def concepts(index: int) -> set[int]:
        return {
            group_index
            for group_index, alternatives in enumerate(critical)
            if any(term in samples[index] for term in alternatives)
        }

    max_windows = max(2, (max_chars - 800) // (window_chars + 110))
    chosen = {0, len(spans) - 1}
    covered = set().union(*(concepts(index) for index in chosen))
    while len(chosen) < min(max_windows, len(spans)):
        candidates = (index for index in range(len(spans)) if index not in chosen)
        index = max(
            candidates,
            key=lambda item: (
                # Reward explicit, first-listed obligation phrases over incidental\n                # mentions such as menu labels, then diversify topics.
                # of the same generic word in several overlapping concepts.
                sum(
                    3 if alternatives[0] in samples[item] else 1
                    for group, alternatives in enumerate(critical)
                    if group not in covered and any(t in samples[item] for t in alternatives)
                ),
                sum(term in samples[item] for term in terms),
                -item,
            ),
        )
        chosen.add(index)
        covered.update(concepts(index))

    excerpts = tuple(SourceExcerpt(role, *spans[i], text[slice(*spans[i])]) for i in sorted(chosen))
    labeled = [
        f"[ИЗВЛЕЧЁННЫЙ ФРАГМЕНТ {part.ref}; НЕ ЯВЛЯЕТСЯ ПРОВЕРЕННОЙ ЦИТАТОЙ]\n{part.text}"
        for part in excerpts
    ]
    result = "\n\n".join(labeled)
    if len(result) > max_chars:
        raise AssertionError("extraction budget unexpectedly exceeded")
    return DocumentContext(text=result, excerpts=excerpts, truncated=True)
