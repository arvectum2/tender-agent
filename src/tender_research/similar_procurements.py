from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field

from src.modules.price_normalization.normalize import normalize_title
from src.modules.tender_operator_agent_demo.relevance_scoring import _inflection_stem
from src.tender_research.models import ProcurementTender
from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository

SignalName = Literal["subject", "positions", "customer", "requirements"]
RetrievalQueryKind = Literal["subject", "positions", "requirements"]

_GENERIC_TOKENS = {
    "для",
    "или",
    "при",
    "это",
    "поставка",
    "поставки",
    "поставку",
    "закупка",
    "закупки",
    "товар",
    "товара",
    "товаров",
    "оказание",
    "услуг",
    "услуги",
    "выполнение",
    "работ",
    "работы",
    "приобретение",
}
_POSITION_CONTAINER_KEYS = {
    "positions",
    "items",
    "purchase_objects",
    "purchaseobjects",
    "products",
    "goods",
}
_REQUIREMENT_CONTAINER_KEYS = {
    "requirements",
    "technical_requirements",
    "key_requirements",
    "requirements_summary",
}
_POSITION_TEXT_KEYS = (
    "name",
    "item_name",
    "product_name",
    "title",
    "description",
    "object_name",
)
_REQUIREMENT_TEXT_KEYS = (
    "detail",
    "text",
    "requirement",
    "title",
    "description",
    "value",
)
_OKPD_KEYS = {
    "okpd",
    "okpd2",
    "okpd_code",
    "okpd2_code",
    "classification_code",
}


class SimilarityEvidence(BaseModel):
    source_type: str
    source_ref: str
    quote: str | None = None
    retrieval_score: float | None = None


class SimilaritySignal(BaseModel):
    signal: SignalName
    available: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    explanation: str
    evidence: list[SimilarityEvidence] = Field(default_factory=list)


class SimilarProcurementItem(BaseModel):
    tender_id: str
    registry_number: str | None = None
    title: str
    customer_name: str | None = None
    customer_inn: str | None = None
    nmck_amount: float | None = None
    currency: str | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)
    score_calculation: str
    signals: list[SimilaritySignal]
    retrieval_evidence: list[SimilarityEvidence] = Field(default_factory=list)


class SimilarProcurementsResponse(BaseModel):
    seed_tender_id: str
    seed_registry_number: str | None = None
    seed_title: str
    candidate_source: str = "DataPlatformRagRetriever.search_all_documents"
    score_calculation: str = (
        "Arithmetic mean of available deterministic domain signals: subject token overlap, "
        "structured position overlap, customer identity match, and structured requirement overlap. "
        "Data Platform hybrid/vector scores generate candidates and evidence but are not silently "
        "mixed into the deterministic similarity score."
    )
    guards_applied: list[str] = Field(
        default_factory=lambda: [
            "exclude_seed_and_same_registry",
            "exclude_identical_content_hash",
            "reject_disjoint_okpd_major_classes_when_both_available",
            "reject_zero_subject_and_zero_or_unknown_position_overlap",
        ]
    )
    rejected_candidates: int = 0
    items: list[SimilarProcurementItem] = Field(default_factory=list)


def _tokens(value: str | None) -> set[str]:
    normalized = normalize_title(value)
    return {
        _inflection_stem(token)
        for token in re.findall(r"[\w-]+", normalized, flags=re.UNICODE)
        if len(token) > 2 and token not in _GENERIC_TOKENS and not token.isdigit()
    }


def _jaccard(left: str | None, right: str | None) -> float | None:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return None
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _flatten_text(values: Iterable[str]) -> str:
    return " ".join(value.strip() for value in values if value and value.strip())[:2000]


def _walk_named_lists(
    value: object,
    container_keys: set[str],
    *,
    path: str = "$",
    depth: int = 0,
) -> list[tuple[str, object]]:
    if depth > 5:
        return []
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_norm = str(key).replace("-", "_").casefold()
            nested_path = f"{path}.{key}"
            if key_norm in container_keys and isinstance(nested, list):
                for index, row in enumerate(nested[:50]):
                    found.append((f"{nested_path}[{index}]", row))
            found.extend(
                _walk_named_lists(
                    nested,
                    container_keys,
                    path=nested_path,
                    depth=depth + 1,
                )
            )
    elif isinstance(value, list):
        for index, row in enumerate(value[:50]):
            found.extend(
                _walk_named_lists(
                    row,
                    container_keys,
                    path=f"{path}[{index}]",
                    depth=depth + 1,
                )
            )
    return found


def _row_text(row: object, keys: tuple[str, ...]) -> str | None:
    if isinstance(row, str):
        return row.strip() or None
    if not isinstance(row, dict):
        return None
    parts: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            parts.append(str(value).strip())
    return " ".join(parts) or None


def _structured_texts(
    tender: ProcurementTender,
    *,
    container_keys: set[str],
    text_keys: tuple[str, ...],
) -> list[tuple[str, str]]:
    raw = tender.raw_payload
    if not isinstance(raw, (dict, list)):
        return []
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for path, row in _walk_named_lists(raw, container_keys):
        text = _row_text(row, text_keys)
        if not text:
            continue
        key = normalize_title(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append((path, text))
    return result[:30]


def _position_texts(tender: ProcurementTender) -> list[tuple[str, str]]:
    return _structured_texts(
        tender,
        container_keys=_POSITION_CONTAINER_KEYS,
        text_keys=_POSITION_TEXT_KEYS,
    )


def _requirement_texts(tender: ProcurementTender) -> list[tuple[str, str]]:
    return _structured_texts(
        tender,
        container_keys=_REQUIREMENT_CONTAINER_KEYS,
        text_keys=_REQUIREMENT_TEXT_KEYS,
    )


def _okpd_major_classes(tender: ProcurementTender) -> set[str]:
    raw = tender.raw_payload
    if not isinstance(raw, (dict, list)):
        return set()
    result: set[str] = set()

    def visit(value: object, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                key_norm = str(key).replace("-", "_").casefold()
                if key_norm in _OKPD_KEYS and isinstance(nested, (str, int, float)):
                    match = re.search(r"\d{2}", str(nested))
                    if match:
                        result.add(match.group(0))
                elif key_norm in {"okpd2_codes", "okpd_codes"} and isinstance(
                    nested, list
                ):
                    for row in nested[:50]:
                        if isinstance(row, dict):
                            code = row.get("code")
                        else:
                            code = row
                        if isinstance(code, (str, int, float)):
                            match = re.search(r"\d{2}", str(code))
                            if match:
                                result.add(match.group(0))
                visit(nested, depth + 1)
        elif isinstance(value, list):
            for row in value[:50]:
                visit(row, depth + 1)

    visit(raw)
    return result


def _combined_overlap(
    left: list[tuple[str, str]],
    right: list[tuple[str, str]],
) -> float | None:
    if not left or not right:
        return None
    left_tokens = _tokens(_flatten_text(text for _, text in left))
    right_tokens = _tokens(_flatten_text(text for _, text in right))
    if not left_tokens or not right_tokens:
        return None
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _customer_signal(
    seed: ProcurementTender,
    candidate: ProcurementTender,
) -> SimilaritySignal:
    evidence: list[SimilarityEvidence] = []
    if seed.customer_inn and candidate.customer_inn:
        same = seed.customer_inn == candidate.customer_inn
        evidence.extend(
            [
                SimilarityEvidence(
                    source_type="PROCUREMENT_TENDER",
                    source_ref=f"{seed.id}:customer_inn",
                    quote=seed.customer_inn,
                ),
                SimilarityEvidence(
                    source_type="PROCUREMENT_TENDER",
                    source_ref=f"{candidate.id}:customer_inn",
                    quote=candidate.customer_inn,
                ),
            ]
        )
        return SimilaritySignal(
            signal="customer",
            available=True,
            score=1.0 if same else 0.0,
            explanation="Exact customer INN match."
            if same
            else "Customer INNs differ.",
            evidence=evidence,
        )
    if seed.customer_name and candidate.customer_name:
        seed_name = normalize_title(seed.customer_name)
        candidate_name = normalize_title(candidate.customer_name)
        same = bool(seed_name and seed_name == candidate_name)
        evidence.extend(
            [
                SimilarityEvidence(
                    source_type="PROCUREMENT_TENDER",
                    source_ref=f"{seed.id}:customer_name",
                    quote=seed.customer_name,
                ),
                SimilarityEvidence(
                    source_type="PROCUREMENT_TENDER",
                    source_ref=f"{candidate.id}:customer_name",
                    quote=candidate.customer_name,
                ),
            ]
        )
        return SimilaritySignal(
            signal="customer",
            available=True,
            score=1.0 if same else 0.0,
            explanation=(
                "Normalized customer names match; INN is unavailable for at least one tender."
                if same
                else "Customer identity does not match on available names; INN is unavailable for at least one tender."
            ),
            evidence=evidence,
        )
    return SimilaritySignal(
        signal="customer",
        available=False,
        score=None,
        explanation="Customer identity is unavailable for deterministic comparison.",
    )


def _text_signal(
    *,
    signal: Literal["subject", "positions", "requirements"],
    score: float | None,
    seed_evidence: list[tuple[str, str]],
    candidate_evidence: list[tuple[str, str]],
    seed_id: str,
    candidate_id: str,
) -> SimilaritySignal:
    label = {
        "subject": "procurement subject",
        "positions": "structured positions",
        "requirements": "structured requirements",
    }[signal]
    if score is None:
        return SimilaritySignal(
            signal=signal,
            available=False,
            score=None,
            explanation=f"{label.capitalize()} are unavailable on one or both tenders.",
        )
    evidence = [
        SimilarityEvidence(
            source_type="PROCUREMENT_TENDER",
            source_ref=f"{seed_id}:{path}",
            quote=text[:280],
        )
        for path, text in seed_evidence[:3]
    ]
    evidence.extend(
        SimilarityEvidence(
            source_type="PROCUREMENT_TENDER",
            source_ref=f"{candidate_id}:{path}",
            quote=text[:280],
        )
        for path, text in candidate_evidence[:3]
    )
    return SimilaritySignal(
        signal=signal,
        available=True,
        score=round(score, 4),
        explanation=f"Deterministic token overlap for {label}: {score:.3f}.",
        evidence=evidence,
    )


def _subject_signal(
    seed: ProcurementTender,
    candidate: ProcurementTender,
) -> SimilaritySignal:
    score = _jaccard(seed.title, candidate.title)
    return _text_signal(
        signal="subject",
        score=score,
        seed_evidence=[("title", seed.title)],
        candidate_evidence=[("title", candidate.title)],
        seed_id=str(seed.id),
        candidate_id=str(candidate.id),
    )


def _retrieval_evidence(
    signal_hits: dict[RetrievalQueryKind, RagSearchHit],
) -> list[SimilarityEvidence]:
    result: list[SimilarityEvidence] = []
    for kind in ("subject", "positions", "requirements"):
        hit = signal_hits.get(kind)
        if hit is None:
            continue
        result.append(
            SimilarityEvidence(
                source_type="DATA_PLATFORM_CHUNK",
                source_ref=f"{hit.chunk_id}:{kind}",
                quote=hit.preview,
                retrieval_score=hit.score,
            )
        )
    return result


def _candidate_queries(
    seed: ProcurementTender,
) -> list[tuple[RetrievalQueryKind, str]]:
    result: list[tuple[RetrievalQueryKind, str]] = []
    if seed.title.strip():
        result.append(("subject", seed.title.strip()))
    positions = _position_texts(seed)
    if positions:
        result.append(("positions", _flatten_text(text for _, text in positions)))
    requirements = _requirement_texts(seed)
    if requirements:
        result.append(("requirements", _flatten_text(text for _, text in requirements)))
    return [(kind, query) for kind, query in result if query.strip()]


def find_similar_procurements(
    repo: TenderRepository,
    retriever,
    *,
    registry_number: str,
    limit: int = 10,
) -> SimilarProcurementsResponse | None:
    seed = repo.get_tender_by_registry_number(registry_number)
    if seed is None:
        return None

    pool_limit = min(100, max(40, limit * 10))
    candidate_hits: dict[str, dict[RetrievalQueryKind, RagSearchHit]] = {}
    for kind, query in _candidate_queries(seed):
        for hit in retriever.search_all_documents(query, limit=pool_limit):
            if hit.tender_id == seed.id:
                continue
            by_signal = candidate_hits.setdefault(hit.tender_id, {})
            previous = by_signal.get(kind)
            if previous is None or hit.score > previous.score:
                by_signal[kind] = hit

    seed_positions = _position_texts(seed)
    seed_requirements = _requirement_texts(seed)
    seed_okpd = _okpd_major_classes(seed)
    items: list[SimilarProcurementItem] = []
    rejected = 0

    for tender_id, signal_hits in candidate_hits.items():
        candidate = repo.get_tender_by_id(tender_id)
        if candidate is None:
            continue
        if candidate.id == seed.id:
            continue
        if (
            seed.registry_number
            and candidate.registry_number
            and seed.registry_number == candidate.registry_number
        ):
            rejected += 1
            continue
        if seed.content_hash and candidate.content_hash == seed.content_hash:
            rejected += 1
            continue

        candidate_okpd = _okpd_major_classes(candidate)
        if seed_okpd and candidate_okpd and seed_okpd.isdisjoint(candidate_okpd):
            rejected += 1
            continue

        subject = _subject_signal(seed, candidate)
        candidate_positions = _position_texts(candidate)
        position_score = _combined_overlap(seed_positions, candidate_positions)
        positions = _text_signal(
            signal="positions",
            score=position_score,
            seed_evidence=seed_positions,
            candidate_evidence=candidate_positions,
            seed_id=str(seed.id),
            candidate_id=str(candidate.id),
        )
        candidate_requirements = _requirement_texts(candidate)
        requirement_score = _combined_overlap(seed_requirements, candidate_requirements)
        requirements = _text_signal(
            signal="requirements",
            score=requirement_score,
            seed_evidence=seed_requirements,
            candidate_evidence=candidate_requirements,
            seed_id=str(seed.id),
            candidate_id=str(candidate.id),
        )
        customer = _customer_signal(seed, candidate)

        subject_score = subject.score or 0.0
        if subject_score == 0.0 and (positions.score is None or positions.score == 0.0):
            rejected += 1
            continue

        signals = [subject, positions, customer, requirements]
        available_scores = [
            signal.score
            for signal in signals
            if signal.available and signal.score is not None
        ]
        if not available_scores:
            rejected += 1
            continue
        score = round(sum(available_scores) / len(available_scores), 4)

        items.append(
            SimilarProcurementItem(
                tender_id=str(candidate.id),
                registry_number=candidate.registry_number,
                title=candidate.title,
                customer_name=candidate.customer_name,
                customer_inn=candidate.customer_inn,
                nmck_amount=candidate.nmck_amount,
                currency=candidate.currency,
                similarity_score=score,
                score_calculation=(
                    f"Arithmetic mean of {len(available_scores)} available deterministic signals."
                ),
                signals=signals,
                retrieval_evidence=_retrieval_evidence(signal_hits),
            )
        )

    items.sort(
        key=lambda item: (
            -item.similarity_score,
            item.registry_number or "",
            item.title,
            item.tender_id,
        )
    )
    return SimilarProcurementsResponse(
        seed_tender_id=str(seed.id),
        seed_registry_number=seed.registry_number,
        seed_title=seed.title,
        rejected_candidates=rejected,
        items=items[:limit],
    )
