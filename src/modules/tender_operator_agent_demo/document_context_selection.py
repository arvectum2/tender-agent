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
    def rank(index: int) -> tuple[int, int]:
        a, b = spans[index]
        sample = text[a:b].lower()
        score = sum(1 for term in terms if term in sample)
        return (score, -index)

    max_windows = max(2, (max_chars - 800) // (window_chars + 110))
    chosen = {0, len(spans) - 1}
    for idx in sorted(range(len(spans)), key=rank, reverse=True):
        if len(chosen) >= max_windows:
            break
        chosen.add(idx)

    excerpts = tuple(SourceExcerpt(role, *spans[i], text[slice(*spans[i])]) for i in sorted(chosen))
    labeled = [
        f"[ИЗВЛЕЧЁННЫЙ ФРАГМЕНТ {part.ref}; НЕ ЯВЛЯЕТСЯ ПРОВЕРЕННОЙ ЦИТАТОЙ]\n{part.text}"
        for part in excerpts
    ]
    result = "\n\n".join(labeled)
    if len(result) > max_chars:
        raise AssertionError("extraction budget unexpectedly exceeded")
    return DocumentContext(text=result, excerpts=excerpts, truncated=True)
