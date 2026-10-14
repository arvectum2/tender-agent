"""Independent full-document retrieval before trusting tender LLM drafts.

The entire extracted source (all roles, not only first-N characters) is
searched. Returned excerpts are exact original-substring pointers, **not**
claims of entailment. Sources and failures remain visible for human review.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

_WORD = re.compile(r"[\wА-Яа-яЁё]{3,}", re.UNICODE)
_MAX_DOCUMENT_CHARS = 2_000_000
_MAX_QUESTIONS = 40
_WINDOW_CHARS = 1080
_HALF_WINDOW = _WINDOW_CHARS // 2


@dataclass(frozen=True)
class ResearchQuestion:
    key: str
    query: str
    anchors: tuple[str, ...]
    roles: tuple[str, ...] = ()
    critical: bool = True


# A repeatable investigation plan is deliberately separate from model prompts.
# It is expandable for new OKPD/domain verticals without rewriting extraction.
STANDARD_QUESTIONS = (
    ResearchQuestion("identity", "Номер и предмет закупки", ("purchasenumber", "номер закупки", "предмет закупки", "purchaseobjectinfo"), ("notice",)),
    ResearchQuestion("price", "НМЦК и порядок изменения цены", ("maxprice", "нмцк", "начальная максимальная цена", "цены контракта", "цену контракта"), ("notice", "contract_draft")),
    ResearchQuestion("submission", "Дата и время окончания подачи", ("enddt", "окончания подачи", "срок подачи заявок", "подачи заявок"), ("notice",)),
    ResearchQuestion("eligibility", "Допуск, СМП/СОНКО, квалификация", ("только субъект", "субъект малого", "социально ориентир", "участник закупки", "preferenserequirement"), ("notice", "technical_spec", "contract_draft")),
    ResearchQuestion("bid_evaluation", "Официальный порядок оценки и определения победителя", ("критерии оценки заявок", "критерии оценки", "порядок оценки", "запрос котировок", "placingway"), ("notice",)),
    ResearchQuestion("performance_security", "Обеспечение исполнения, исключения и гарантии", ("обеспечение исполнения", "независимая гарантия", "размер обеспечения"), ("notice", "contract_draft")),
    ResearchQuestion("scope", "Состав работ, результаты и этапы", ("должен", "исполнитель обязан", "результат оказания", "требования к", "услуг должно"), ("technical_spec",)),
    ResearchQuestion("functional_requirements", "Функциональность, пользователи, внешние сервисы", ("функционал", "продажа билетов", "билетов", "интеграц", "слабовид", "доступност"), ("technical_spec",)),
    ResearchQuestion("acceptance", "Приёмка и необходимые документы", ("порядок приемки", "документ о приемке", "приёмк", "акт приема", "акт при"), ("contract_draft", "technical_spec")),
    ResearchQuestion("payment", "Оплата, аванс, задержки", ("оплата по контракту", "авансирование", "бюджетного финансирования", "рабочих дней", "порядок расчет"), ("contract_draft",)),
    ResearchQuestion("price_adjustment", "Основания и пределы изменения цены/объёма", ("изменение цены", "изменения цены", "пропорционально", "объем", "объёма услуг", "соглашению сторон"), ("contract_draft",)),
    ResearchQuestion("intellectual_property", "Исключительные права и лицензии", ("исключительные права", "исключительных прав", "права передаются", "интеллектуальной деятельности"), ("contract_draft", "technical_spec")),
    ResearchQuestion("warranty", "Гарантия, сроки реагирования и устранения", ("гарантий", "неисправност", "срок устранения", "рабочих дней"), ("technical_spec", "contract_draft")),
    ResearchQuestion("liability", "Штрафы, расторжение, убытки", ("неустойк", "штраф", "расторжен", "отказ от исполнения", "убытк"), ("contract_draft",)),
    ResearchQuestion("delivery", "Сроки и места исполнения", ("срок оказания", "место оказания", "срок исполнения", "сроки оказания"), ("technical_spec", "contract_draft")),
)


def _string(value: Any) -> str:
    return str(value or "").strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _anchor_positions(text: str, anchors: tuple[str, ...]) -> list[tuple[int, str]]:
    """All complete-document matches, bounded in output but not in scanning."""
    lowered = text.casefold().replace("ё", "е")
    positions: list[tuple[int, str]] = []
    for anchor in anchors:
        needle = anchor.casefold().replace("ё", "е")
        if not needle:
            continue
        begin = 0
        while True:
            at = lowered.find(needle, begin)
            if at < 0:
                break
            positions.append((at, anchor))
            begin = at + max(1, len(needle))
            if len(positions) >= 6000:
                return positions
    return positions


def _document_inventory(
    documents: Iterable[Any], manifest: Iterable[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    complete: list[dict[str, Any]] = []
    for idx, item in enumerate(documents):
        file_id = _string(getattr(item, "file_id", None)) or f"missing-file-id-{idx}"
        role = _string(getattr(item, "role", None)) or "supporting"
        name = _string(getattr(item, "display_name", None)) or file_id
        body = getattr(item, "text", None)
        text = body if isinstance(body, str) else ""
        has_text = bool(text.strip())
        too_large = len(text) > _MAX_DOCUMENT_CHARS
        status = "OVERSIZE_UNREVIEWED" if too_large else ("EXTRACTED" if has_text else "UNEXTRACTED")
        row = {
            "file_id": file_id, "role": role, "document": name,
            "text_sha256": _digest(text) if has_text else None,
            "text_length": len(text), "status": status,
        }
        rows.append(row)
        if has_text and not too_large:
            complete.append({**row, "text": text})
    known = {row["file_id"] for row in rows}
    if manifest:
        for item in manifest:
            file_id = _string(item.get("file_id"))
            if file_id and file_id not in known:
                rows.append({
                    "file_id": file_id,
                    "role": _string(item.get("role_hint") or item.get("document_kind")) or "unknown",
                    "document": _string(item.get("display_name") or item.get("original_name")) or file_id,
                    "text_sha256": None, "text_length": 0, "status": "NOT_PROCESSED",
                })
    return rows, complete


def _find_source_evidence(
    question: ResearchQuestion, documents: list[dict[str, Any]], *, limit: int = 4,
) -> list[dict[str, Any]]:
    candidates: list[tuple[float, str, int, dict[str, Any]]] = []
    for doc in documents:
        text = doc["text"]
        matches = _anchor_positions(text, question.anchors)
        if not matches:
            continue
        positions: dict[tuple[int, int], set[str]] = {}
        for at, anchor in matches:
            start = max(0, at - _HALF_WINDOW)
            end = min(len(text), start + _WINDOW_CHARS)
            # Avoid near-duplicate windows for the same paragraph.
            group = (at // 700, min(len(text), at // 700 * 700 + 1200))
            positions.setdefault(group, set()).add(anchor)
        for (group, _), matched in positions.items():
            center = group * 700 + 350
            start = max(0, center - _HALF_WINDOW)
            end = min(len(text), start + _WINDOW_CHARS)
            passage = text[start:end]
            matched_in_passage = tuple(a for a in question.anchors if a.casefold().replace("ё", "е") in passage.casefold().replace("ё", "е"))
            score = (4.0 if doc["role"] in question.roles else 0.0) + len(matched_in_passage) * 3
            score += len(set(_WORD.findall(question.query.casefold())) & set(_WORD.findall(passage.casefold()))) * 0.1
            hit = {
                "file_id": doc["file_id"], "document": doc["document"],
                "role": doc["role"], "source_sha256": doc["text_sha256"],
                "start": start, "end": end,
                "source_ref": f"normalized:{doc['file_id']}:{start}-{end}",
                "quote": passage, "quote_sha256": _digest(passage),
                "anchors": list(matched_in_passage),
                "semantic_status": "UNVERIFIED_CONTEXT_ONLY",
            }
            candidates.append((score, doc["file_id"], start, hit))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    out: list[dict[str, Any]] = []
    chosen: list[tuple[str, int, int]] = []
    for _, file_id, start, hit in candidates:
        if any(fid == file_id and abs(start - prior) < 550 for fid, prior, _ in chosen):
            continue
        out.append(hit)
        chosen.append((file_id, start, hit["end"]))
        if len(out) >= limit:
            break
    return out


def research_full_corpus(
    documents: Iterable[Any],
    *,
    manifest: Iterable[Mapping[str, Any]] | None = None,
    questions: Iterable[ResearchQuestion] = STANDARD_QUESTIONS,
    max_hits_per_topic: int = 4,
) -> dict[str, Any]:
    """Find where sources talk about each question, not whether LLM is right.

    This search scans all extracted text of every input file (not an LLM window).
    A hit is a precise original-text quote, never semantic verification.
    """
    qs = tuple(questions)
    if len(qs) > _MAX_QUESTIONS or max_hits_per_topic not in range(1, 9):
        raise ValueError("research budget exceeded")
    inventory, complete = _document_inventory(documents, manifest)
    findings: list[dict[str, Any]] = []
    for q in qs:
        hits = _find_source_evidence(q, complete, limit=max_hits_per_topic)
        findings.append({
            "key": q.key, "question": q.query,
            "status": "SOURCE_CONTEXT_FOUND_REVIEW" if hits else "NOT_FOUND_IN_EXTRACTED_TEXT",
            "required_human_review": True, "hits": hits,
        })
    problem_files = [row["file_id"] for row in inventory if row["status"] != "EXTRACTED"]
    missing_topics = [f["key"] for f in findings if not f["hits"]]
    return {
        "version": 1, "source_status": "INCOMPLETE" if problem_files else "EXTRACTED_NOT_SEMANTICALLY_VERIFIED",
        "document_count": len(inventory), "extracted_document_count": len(complete),
        "unread_file_ids": problem_files, "missing_research_topics": missing_topics,
        "documents": inventory, "findings": findings,
        "overall_decision": "HUMAN_REVIEW_REQUIRED",
        "source_truth_attested": False,
        "llm_claims_verified": False,
    }


def examine_llm_assertions(
    research: Mapping[str, Any],
    assertions: Iterable[str],
    *,
    max_assertions: int = 80,
) -> list[dict[str, Any]]:
    """Attach relevant source locations WITHOUT promoting keyword overlap.

    An exact source fragment validates *only its own bytes*, never the meaning
    of a paraphrased claim; legal interpretation always stays unverified.
    """
    by_topic = list(research.get("findings") or [])
    out: list[dict[str, Any]] = []
    for claim in list(assertions)[:max_assertions]:
        phrase = _string(claim)
        if not phrase:
            continue
        tokens = set(_WORD.findall(phrase.casefold()))
        ranked: list[tuple[int, str]] = []
        for finding in by_topic:
            for hit in finding.get("hits") or []:
                words = set(_WORD.findall(_string(hit.get("quote")).casefold()))
                overlap = len(tokens & words)
                if overlap >= 2 and (not tokens or overlap / len(tokens) >= 0.15):
                    ranked.append((overlap, _string(hit.get("source_ref"))))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        out.append({
            "claim": phrase[:600],
            "status": "SOURCE_LOCATIONS_TO_REVIEW" if ranked else "NO_MATCH_IN_INDEXED_SNIPPETS",
            "semantic_verification": "NOT_PERFORMED",
            "source_refs": [ref for _, ref in ranked[:3]],
            "requires_human_review": True,
        })
    return out
