from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .supplier_profile import SupplierProfile


class RelevanceStatus(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_RECOMMENDED = "not_recommended"


class RelevanceRecommendation(StrEnum):
    PARTICIPATE = "participate"
    PARTICIPATE_CONDITIONALLY = "participate_conditionally"
    DO_NOT_PARTICIPATE = "do_not_participate"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass(frozen=True)
class RelevanceScoreResult:
    score: float
    status: RelevanceStatus
    recommendation: RelevanceRecommendation
    reasons: list[str]
    breakdown: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "status": self.status.value,
            "recommendation": self.recommendation.value,
            "reasons": self.reasons,
            "breakdown": self.breakdown,
        }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[0-9a-zа-яё]+", _normalize(text), flags=re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return set(_words(text))


# Conservative inflection endings.  This is deliberately not a generic
# Russian stemmer: the discovery baseline showed that a broad 7-character
# prefix incorrectly treated derivationally different words such as
# ``автоматизация`` and ``автоматизированной`` as the same capability.
_INFLECTION_SUFFIXES = tuple(
    sorted(
        {
            "иями",
            "ями",
            "ами",
            "его",
            "ого",
            "ему",
            "ому",
            "ими",
            "ыми",
            "иях",
            "ах",
            "ях",
            "ию",
            "ью",
            "ия",
            "ья",
            "ую",
            "юю",
            "ая",
            "яя",
            "ое",
            "ее",
            "ие",
            "ые",
            "ий",
            "ый",
            "ой",
            "им",
            "ым",
            "ом",
            "ем",
            "их",
            "ых",
            "ов",
            "ев",
            "ам",
            "ям",
            "а",
            "я",
            "ы",
            "и",
            "у",
            "ю",
            "е",
            "о",
        },
        key=len,
        reverse=True,
    )
)


def _inflection_stem(word: str) -> str:
    normalized = _normalize(word)
    for suffix in _INFLECTION_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 5:
            return normalized[: -len(suffix)]
    return normalized


def _word_matches(title_tokens: set[str], word: str) -> bool:
    normalized = _normalize(word)
    if len(normalized) < 3:
        return normalized in title_tokens
    stem = _inflection_stem(normalized)
    for token in title_tokens:
        if token == normalized:
            return True
        # Preserve safe compounds/ordinary inflections such as
        # ``кабель`` -> ``кабельной`` and ``оборудование`` ->
        # ``электрооборудования`` without broad prefix matching.
        shorter, longer = (normalized, token) if len(normalized) <= len(token) else (token, normalized)
        if len(shorter) >= 5 and shorter in longer:
            return True
        if len(stem) >= 5 and stem == _inflection_stem(token):
            return True
    return False


def _all_words_match(title_tokens: set[str], phrase: str) -> bool:
    words = [word for word in _words(phrase) if len(word) >= 3]
    if not words:
        return False
    return all(_word_matches(title_tokens, word) for word in words)


def _keyword_matches_title(title_tokens: set[str], keyword: str) -> bool:
    return _all_words_match(title_tokens, keyword)


def _stop_word_matches_title(title_tokens: set[str], stop_word: str) -> bool:
    return _all_words_match(title_tokens, stop_word)


def _semantic_match_score(
    title: str,
    keywords: list[str],
    categories: list[str],
) -> tuple[float, float, list[str]]:
    """Return keyword score, category bonus, and source-visible reasons.

    The frozen DISCOVERY-QA-001 baseline demonstrated that ratio-to-all-keywords
    diluted one clear capability match to 5-10 points while unrelated in-range
    procurements received 45 neutral/commercial points.  A clear keyword match
    therefore gets a strong fixed base; additional matches add only bounded
    evidence.  Full category phrases are a small bonus, not a second base score.
    """

    tokens = _tokens(title)
    matched_keywords = [kw for kw in keywords if _keyword_matches_title(tokens, kw)]
    matched_categories = [category for category in categories if _all_words_match(tokens, category)]
    reasons: list[str] = []

    if matched_keywords:
        keyword_score = min(35.0 + 5.0 * (len(matched_keywords) - 1), 45.0)
        reasons.extend(f"Совпадение с профилем: «{kw}»" for kw in matched_keywords)
    else:
        keyword_score = 0.0

    category_bonus = min(10.0 + 5.0 * (len(matched_categories) - 1), 15.0) if matched_categories else 0.0
    reasons.extend(f"Совпадение категории: «{category}»" for category in matched_categories)

    if keyword_score == 0.0 and category_bonus == 0.0:
        reasons.append("Тематические признаки профиля поставщика не найдены в названии закупки")
    return keyword_score, category_bonus, reasons


def _stop_word_penalty(title: str, stop_words: list[str]) -> tuple[float, list[str]]:
    if not stop_words:
        return 0.0, []
    tokens = _tokens(title)
    score = 0.0
    reasons: list[str] = []
    for stop_word in stop_words:
        if _stop_word_matches_title(tokens, stop_word):
            score -= 15.0
            reasons.append(f"Стоп-слово в названии: «{stop_word}»")
    return score, reasons


def _price_range_score(
    price: float | None,
    price_min: float | None,
    price_max: float | None,
    *,
    semantic_match: bool,
) -> tuple[float, list[str]]:
    if not semantic_match:
        return 0.0, ["Цена не повышает релевантность без тематического совпадения"]
    if price is None:
        return 5.0, ["Цена не указана — частичный балл"]
    reasons: list[str] = []
    if price_min is not None and price_max is not None:
        if price_min <= price <= price_max:
            reasons.append(f"Цена {price:,.0f} ₽ в диапазоне поставщика {price_min:,.0f}–{price_max:,.0f} ₽")
            return 20.0, reasons
        if price < price_min:
            reasons.append(f"Цена {price:,.0f} ₽ ниже минимальной {price_min:,.0f} ₽")
            return 5.0, reasons
        reasons.append(f"Цена {price:,.0f} ₽ выше максимальной {price_max:,.0f} ₽")
        return 5.0, reasons
    if price_min is not None:
        if price >= price_min:
            reasons.append(f"Цена {price:,.0f} ₽ не ниже минимальной {price_min:,.0f} ₽")
            return 15.0, reasons
        reasons.append(f"Цена {price:,.0f} ₽ ниже минимальной {price_min:,.0f} ₽")
        return 5.0, reasons
    if price_max is not None:
        if price <= price_max:
            reasons.append(f"Цена {price:,.0f} ₽ не выше максимальной {price_max:,.0f} ₽")
            return 15.0, reasons
        reasons.append(f"Цена {price:,.0f} ₽ выше максимальной {price_max:,.0f} ₽")
        return 5.0, reasons
    return 0.0, []


def _deadline_score(
    submission_deadline: str | None,
    max_delay_days: int | None,
    *,
    semantic_match: bool,
) -> tuple[float, list[str]]:
    del max_delay_days  # card-level scorer does not yet parse execution delay semantics
    if not semantic_match:
        return 0.0, ["Срок подачи не повышает релевантность без тематического совпадения"]
    if not submission_deadline:
        return 5.0, ["Срок подачи не указан — частичный балл"]
    return 10.0, []


def _risk_flag_score(
    title: str,
    customer_name: str | None,
    risk_preferences: object,
) -> tuple[float, list[str]]:
    del title, customer_name, risk_preferences
    # The previous implementation granted every card +15 simply because no
    # card-level risk check existed.  The frozen discovery baseline proved that
    # this promoted unrelated procurements.  Unknown risk is neutral, not good.
    return 0.0, ["Риск-факторы не оцениваются по поисковой карточке"]


def score_procurement_card(
    *,
    title: str,
    initial_price: float | None = None,
    customer_name: str | None = None,
    submission_deadline: str | None = None,
    profile: SupplierProfile | None = None,
) -> RelevanceScoreResult:
    if profile is None:
        return RelevanceScoreResult(
            score=0.0,
            status=RelevanceStatus.NOT_RECOMMENDED,
            recommendation=RelevanceRecommendation.MANUAL_REVIEW_REQUIRED,
            reasons=["Профиль поставщика не загружен — скоринг недоступен"],
            breakdown={},
        )

    breakdown: dict[str, float] = {}
    all_reasons: list[str] = []

    keyword_score, category_bonus, semantic_reasons = _semantic_match_score(
        title,
        profile.criteria.keywords,
        profile.criteria.categories,
    )
    breakdown["keywords"] = round(keyword_score, 1)
    breakdown["categories"] = round(category_bonus, 1)
    all_reasons.extend(semantic_reasons)
    semantic_match = keyword_score > 0.0 or category_bonus > 0.0

    stop_penalty, stop_reasons = _stop_word_penalty(title, profile.criteria.stop_words)
    breakdown["stop_words"] = round(stop_penalty, 1)
    all_reasons.extend(stop_reasons)

    price_score, price_reasons = _price_range_score(
        initial_price,
        profile.criteria.price_min,
        profile.criteria.price_max,
        semantic_match=semantic_match,
    )
    breakdown["price_range"] = round(price_score, 1)
    all_reasons.extend(price_reasons)

    deadline_score, deadline_reasons = _deadline_score(
        submission_deadline,
        profile.risk_preferences.max_delay_days,
        semantic_match=semantic_match,
    )
    breakdown["deadline"] = round(deadline_score, 1)
    all_reasons.extend(deadline_reasons)

    risk_score, risk_reasons = _risk_flag_score(title, customer_name, profile.risk_preferences)
    breakdown["risk"] = round(risk_score, 1)
    all_reasons.extend(risk_reasons)

    total = sum(breakdown.values())
    total = max(0.0, min(total, 100.0))

    if total >= 65:
        status = RelevanceStatus.HIGH
        recommendation = RelevanceRecommendation.PARTICIPATE
    elif total >= 40:
        status = RelevanceStatus.MEDIUM
        recommendation = RelevanceRecommendation.PARTICIPATE_CONDITIONALLY
    elif total >= 20:
        status = RelevanceStatus.LOW
        recommendation = RelevanceRecommendation.MANUAL_REVIEW_REQUIRED
    else:
        status = RelevanceStatus.NOT_RECOMMENDED
        recommendation = RelevanceRecommendation.DO_NOT_PARTICIPATE

    return RelevanceScoreResult(
        score=round(total, 1),
        status=status,
        recommendation=recommendation,
        reasons=all_reasons,
        breakdown=breakdown,
    )

def score_procurement_document_text(
    *,
    text: str,
    profile: SupplierProfile | None = None,
) -> dict:
    if profile is None:
        return {
            "document_score": 0.0,
            "document_match_found": False,
            "document_reasons": ["Профиль поставщика не загружен"],
            "document_matched_terms": [],
        }
    tokens = _tokens(text)
    matched_terms: list[str] = []
    for kw in profile.criteria.keywords:
        if _all_words_match(tokens, kw):
            matched_terms.append(kw)
    for cert in profile.certificates:
        if _all_words_match(tokens, cert):
            matched_terms.append(cert)
    score = min(len(matched_terms) * 10.0, 100.0)
    return {
        "document_score": round(score, 1),
        "document_match_found": score >= 20.0,
        "document_reasons": (
            [f"Найдено совпадений: {len(matched_terms)} терминов"] if matched_terms
            else ["Совпадений по тексту документа не найдено"]
        ),
        "document_matched_terms": matched_terms,
    }
