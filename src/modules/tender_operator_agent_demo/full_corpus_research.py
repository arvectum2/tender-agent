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
            # Do not terminate the *whole* scan when one common anchor repeats:
            # later, more specific obligations must remain discoverable.
            # The final evidence list is bounded independently.
    return positions


def _document_inventory(
    documents: Iterable[Any], manifest: Iterable[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    complete: list[dict[str, Any]] = []
    manifest_rows = list(manifest or ())
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    for manifest_item in manifest_rows:
        key = _string(manifest_item.get("file_id")).casefold()
        if key:
            by_id.setdefault(key, []).append(manifest_item)

    document_rows = list(documents)
    document_id_counts: dict[str, int] = {}
    for document in document_rows:
        identifier = _string(getattr(document, "file_id", None)).casefold()
        if identifier:
            document_id_counts[identifier] = document_id_counts.get(identifier, 0) + 1
    for idx, item in enumerate(document_rows):
        file_id = _string(getattr(item, "file_id", None)) or f"missing-file-id-{idx}"
        role = _string(getattr(item, "role", None)) or "supporting"
        name = _string(getattr(item, "display_name", None)) or file_id
        body = getattr(item, "text", None)
        text = body if isinstance(body, str) else ""
        has_text = bool(text.strip())
        too_large = len(text) > _MAX_DOCUMENT_CHARS
        computed_text_sha = _digest(text) if has_text else None
        raw = getattr(item, "raw_content", None)
        computed_raw_sha = hashlib.sha256(raw).hexdigest() if isinstance(raw, bytes) else None
        receipts = by_id.get(file_id.casefold(), [])
        receipt = receipts[0] if len(receipts) == 1 else {}
        expected_text_sha = _string(
            receipt.get("normalized_text_sha256") or receipt.get("text_sha256")
        ).lower()
        expected_raw_sha = _string(receipt.get("raw_sha256")).lower()
        provided = [value for value in (expected_text_sha, expected_raw_sha) if value]
        invalid_receipts = any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in provided)
        mismatch = (
            bool(expected_text_sha and expected_text_sha != computed_text_sha)
            or bool(expected_raw_sha and expected_raw_sha != computed_raw_sha)
        )
        if document_id_counts.get(file_id.casefold(), 0) > 1:
            status = "DUPLICATE_SOURCE_ID_UNREVIEWED"
        elif len(receipts) > 1:
            status = "DUPLICATE_MANIFEST_ID_UNREVIEWED"
        elif invalid_receipts:
            status = "INVALID_SHA_RECEIPT_UNREVIEWED"
        elif mismatch:
            status = "HASH_MISMATCH_UNREVIEWED"
        elif too_large:
            status = "OVERSIZE_UNREVIEWED"
        elif not has_text:
            status = "UNEXTRACTED"
        else:
            status = "EXTRACTED"
        row = {
            "file_id": file_id, "role": role, "document": name,
            "text_sha256": computed_text_sha, "raw_sha256": computed_raw_sha,
            "text_length": len(text), "status": status,
            "receipt_status": (
                "MATCHED_DECLARED_DIGEST" if provided and status == "EXTRACTED"
                else "NO_DECLARED_DIGEST" if not provided and status == "EXTRACTED"
                else "NOT_VERIFIED"
            ),
        }
        rows.append(row)
        if status == "EXTRACTED":
            complete.append({**row, "text": text})
    known = {row["file_id"].casefold() for row in rows}
    if manifest_rows:
        for item in manifest_rows:
            file_id = _string(item.get("file_id"))
            if file_id and file_id.casefold() not in known:
                rows.append({
                    "file_id": file_id,
                    "role": _string(item.get("role_hint") or item.get("document_kind")) or "unknown",
                    "document": _string(item.get("display_name") or item.get("original_name")) or file_id,
                    "text_sha256": None, "raw_sha256": None,
                    "text_length": 0, "status": "NOT_PROCESSED",
                    "receipt_status": "NOT_VERIFIED",
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
        positions: set[int] = set()
        for at, anchor in matches:
            start = max(0, at - _HALF_WINDOW)
            end = min(len(text), start + _WINDOW_CHARS)
            # Avoid near-duplicate windows for the same paragraph.
            positions.add(at // 700)
        for group in positions:
            center = group * 700 + 350
            start = max(0, center - _HALF_WINDOW)
            end = min(len(text), start + _WINDOW_CHARS)
            passage = text[start:end]
            matched_in_passage = tuple(a for a in question.anchors if a.casefold().replace("ё", "е") in passage.casefold().replace("ё", "е"))
            score = (4.0 if doc["role"] in question.roles else 0.0) + len(matched_in_passage) * 3
            # First query anchor is the authoritative/most specific form
            # (e.g. XML maxPrice) and should beat dozens of generic references
            # to "price" elsewhere in the same document.
            if question.anchors[0] in matched_in_passage:
                score += 12
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

    def add(row: tuple[float, str, int, dict[str, Any]]) -> None:
        _, file_id, start, hit = row
        if any(fid == file_id and abs(start - prior) < 550 for fid, prior, _ in chosen):
            return
        out.append(hit)
        chosen.append((file_id, start, hit["end"]))

    # A claim about price or bidder eligibility cannot rely on contract snippets
    # alone when a separately sourced EIS notice is available. Reserve at
    # least one slot for each explicitly relevant document role.
    for role in question.roles:
        if len(out) >= limit:
            break
        best = next((row for row in candidates if row[3]["role"] == role), None)
        if best is not None:
            add(best)
    for row in candidates:
        if len(out) >= limit:
            break
        add(row)
    return out



def _structured_xml_notice_facts(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse source-defined official fields, never infer revision freshness."""
    from src.modules.tender_operator_agent_demo.eis_notice_parser import (
        extract_notice_metadata,
        extract_notice_revision_info,
    )

    found: list[dict[str, Any]] = []
    for doc in documents:
        if doc["role"] != "notice" or not doc["text"].lstrip().startswith("<"):
            continue
        # Reject missing/ambiguous registry identities and unsafe XML before
        # treating any value as a source-defined fact.
        revision = extract_notice_revision_info(doc["text"])
        if not revision.get("purchase_number"):
            continue
        parsed = extract_notice_metadata(doc["text"])
        if not parsed.get("_has_notice_data"):
            continue
        for field in ("nmck", "submission_deadline", "publication_date", "procurement_subject"):
            value = parsed.get(field)
            if value is None or value == "":
                continue
            found.append({
                "field": field, "value": value,
                "file_id": doc["file_id"],
                "source_sha256": doc["text_sha256"],
                "procurement_number": revision["purchase_number"],
                "document_published_at": revision.get("published_at"),
                "source_status": "ORIGINAL_XML_EXTRACTED_NOT_CURRENT_ATTESTED",
                "requires_human_review": True,
            })
    return found


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
    structured_facts = _structured_xml_notice_facts(complete)
    findings: list[dict[str, Any]] = []
    for q in qs:
        hits = _find_source_evidence(q, complete, limit=max_hits_per_topic)
        findings.append({
            "key": q.key, "question": q.query,
            "status": "SOURCE_CONTEXT_FOUND_REVIEW" if hits else "NOT_FOUND_IN_EXTRACTED_TEXT",
            "required_human_review": True, "hits": hits,
        })
    problem_files = [row["file_id"] for row in inventory if row["status"] != "EXTRACTED"]
    notice_files = {row["file_id"] for row in complete if row["role"] == "notice"}
    # Multiple archived notices may describe different revisions. Only an
    # independently pinned official revision can settle precedence.
    revision_ambiguous = len(notice_files) > 1
    missing_topics = [f["key"] for f in findings if not f["hits"]]
    source_status = (
        "INCOMPLETE" if problem_files
        else "MULTIPLE_NOTICE_REVISIONS_REVIEW" if revision_ambiguous
        else "EXTRACTED_NOT_SEMANTICALLY_VERIFIED"
    )
    return {
        "version": 1, "source_status": source_status,
        "multiple_notices_require_revision_resolution": revision_ambiguous,
        "document_count": len(inventory), "extracted_document_count": len(complete),
        "unread_file_ids": problem_files, "missing_research_topics": missing_topics,
        "documents": inventory, "structured_notice_facts": structured_facts,
        "findings": findings,
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


def build_research_brief(
    research: Mapping[str, Any], *, max_chars: int = 11500,
) -> dict[str, Any]:
    """Bounded multi-question context from ALL scanned source documents.

    We do not drop the original full-index metadata or mark these quotations as
    verified. The brief is a separate, non-authoritative evidence input to
    the model in addition to its legacy notice/spec/contract excerpts.
    """
    if max_chars < 1200:
        raise ValueError("research brief budget too small")
    intro = (
        "SOURCE RESEARCH — ORIGINAL FRAGMENTS, NOT VERIFIED CLAIMS. "
        "Check each statement against its quoted source. Do not invent "
        "evaluation criteria, bidder eligibility, price, dates or terms. "
        "Source paragraphs can contradict each other or be obsolete; "
        "if so report UNKNOWN and require human review."
    )
    sections = [intro]
    used = len(intro)
    # Model-visible source-defined XML facts take precedence over guesses from
    # prose; provenance does not attest that this is the latest EIS revision.
    notice_facts = list(research.get("structured_notice_facts") or [])[:12]
    if notice_facts:
        header = "ORIGINAL EIS XML FIELDS — historical source, NOT current authority: "
        values = "; ".join(
            f"{item['field']}={item['value']} (source={item['file_id']})"
            for item in notice_facts
        )
        section = header + values
        sections.append(section[:min(900, max_chars // 9)])
        used += len(sections[-1]) + 2
    missing: list[str] = []
    for question in research.get("findings") or []:
        hits = question.get("hits") or []
        if not hits:
            missing.append(_string(question.get("key")))
            continue
        # Per-question fair-share prevents e.g. generic scope from consuming
        # the whole budget before later risk/contract questions.
        remaining_topics = max(1, len(research.get("findings") or []) - len(sections) + 1)
        budget = min(650, max(220, (max_chars - used) // remaining_topics))
        if used + budget >= max_chars:
            missing.append(_string(question.get("key")))
            continue
        hit = hits[0]
        heading = (
            f"[{question['key']} | source={hit['source_ref']} "
            f"| sha256={hit['source_sha256'][:14]} | HUMAN CHECK REQUIRED]\n"
        )
        text = _string(hit.get("quote"))
        payload = heading + text[:max(0, budget - len(heading))]
        sections.append(payload)
        used += len(payload) + 2
    return {
        "version": 1,
        "source_status": research.get("source_status"),
        "original_document_count": research.get("document_count", 0),
        "unread_file_ids": list(research.get("unread_file_ids") or []),
        "uncovered_research_topics": sorted(
            set(missing + list(research.get("missing_research_topics") or []))
        ),
        "source_evidence_brief": "\n\n".join(sections)[:max_chars],
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "semantic_verification": "NOT_PERFORMED",
    }
