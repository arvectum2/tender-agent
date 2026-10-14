"""Source-attested, non-decisional material-condition leads across all 96 originals.

Only literal topical signals, not legal duties/eligibility/GO. Read-only private
text inputs have pinned receipts and are matched to the selected notice edition.
Public output never contains filesystem paths, UIDs or surrounding source text.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_additional_original_claims import (
    PINS,
    _trusted_private_file,
    pinned,
)
from src.modules.tender_operator_agent_demo.r4_all_original_text_coverage import (
    _FRESH25_SHA,
    _PRIOR50_SHA,
    _read_original_text_receipt,
    _verify_text_location,
)

# These patterns trigger *questions*, not confirmed legal requirements.
TOPICS = (
    ("Обеспечение заявки/контракта", r"обеспечени[ея]\s+(?:исполнения\s+)?(?:контракта|заявки|договора)"),
    ("Права на ПО и результаты", r"(?:исключительн\w*\s+прав\w*|лицензионн\w*\s+договор\w*|правообладател\w*)"),
    ("Лицензирование/квалификация", r"(?:лицензи[яию]\s+на\s+\w+|аккредитаци\w*|членств\w*\s+в\s+СРО)"),
    ("Персональные данные и ИБ", r"(?:персональн\w*\s+данн\w*|ФСТЭК|защит\w*\s+информаци\w*)"),
    ("Сроки исполнения", r"(?:срок\w*\s+(?:выполнения\s+работ|оказания\s+услуг|исполнения\s+контракта)|календарн\w*\s+дн\w*)"),
    ("Приёмка результата", r"(?:при[её]мк\w*\s+(?:услуг|работ|результатов)|акт\w*\s+(?:сдачи|при[её]мки))"),
    ("Оплата и аванс", r"(?:порядок\s+оплаты|авансировани\w*|предоплат\w*)"),
    ("Гарантийные обязательства", r"(?:гарантийн\w*\s+(?:срок|обязательств|обслуживан)|устранени\w*\s+(?:дефектов|недостатков))"),
)
_PATTERNS = [(name, re.compile(p, re.IGNORECASE)) for name, p in TOPICS]

# Source snippets independently inspected on the immutable first-party corpus.
# These are archival textual statements for expert review, never legal/Owner GO.
_VERIFIED_NONREQUIREMENT_SNIPPETS = (
    ("0127100008626000013", "Оплата и аванс", "Авансирование не предусмотрено."),
    ("0149200002326001555", "Оплата и аванс", "Авансирование не предусмотрено."),
    (
        "0151600003226000011",
        "Гарантийные обязательства",
        "Гарантийный срок на оказываемые по Контракту Услуги не установлен",
    ),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


_NEGATION_CUES = re.compile(
    r"\bне\s+(?:требует(?:ся)?|предусмотрен\w*|установлен\w*|"
    r"применя\w*|явля\w*\s+обязательн\w*|допуска\w*)\b"
    r"|\bбез\s+(?:обеспечения|лицензии)\b",
    re.IGNORECASE,
)
_DUTY_CUES = re.compile(
    r"\b(?:обязан\w*|должен|должна|должны|требует(?:ся)?|"
    r"предоставить|представить|предусмотрен\w*|установлен\w*|"
    r"составляет|осуществляется|передает|подписывает)\b",
    re.IGNORECASE,
)
_LOCATOR = re.compile(r"PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+")


def _local_context(text: str, start: int, end: int) -> tuple[str, int, int, str]:
    """Bounded source around a literal mention, never treat it as a complete legal clause."""
    line_start = text.rfind("\n", 0, start) + 1
    next_line = text.find("\n", end)
    line_end = len(text) if next_line < 0 else next_line
    # Long flattened DOC/PDF paragraphs are never published; cap context for evidence flags.
    left = max(line_start, start - 140)
    right = min(line_end, end + 140)
    if right - left > 360:
        right = left + 360
    segment = text[left:right]
    if not text[start:end] or text[start:end] not in segment:
        raise ValueError("literal candidate context cannot be located")
    line = text[line_start:line_end].strip()
    label = "CONTEXT_UNCERTAIN"
    # Negation from the PREVIOUS or NEXT sentence must never negate this topic.
    relative_start, relative_end = start - left, end - left
    previous = max(
        (segment.rfind(delimiter, 0, relative_start)
         for delimiter in ".;!?\n"),
        default=-1,
    )
    following = [
        position for delimiter in ".;!?\n"
        if (position := segment.find(delimiter, relative_end)) >= 0
    ]
    sentence = segment[previous + 1:min(following, default=len(segment))]
    if _NEGATION_CUES.search(sentence):
        label = "NEGATION_CUE_NEAR_MENTION"
    elif len(line) <= 115 and not _DUTY_CUES.search(line) and not line.endswith((".", ";", ":", "!")):
        label = "POSSIBLE_HEADING_OR_TABLE_LABEL"
    elif _DUTY_CUES.search(segment):
        label = "OBLIGATION_VERB_NEAR_MENTION"
    return segment, left, right, label


def literal_candidates(text: str) -> list[dict]:
    """First literal mention of each topic and bounded context flags, not legal findings."""
    result = []
    original_text_sha = _sha(text.encode("utf8"))
    for title, pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        locators = list(_LOCATOR.finditer(text, 0, match.start()))
        anchor = (locators[-1].group(0) if locators
                  else f"Строка {text.count(chr(10), 0, match.start()) + 1}")
        local, lo, hi, flag = _local_context(text, match.start(), match.end())
        result.append({
            "review_topic": title,
            "literal_text": match.group(0),
            "source_locator": anchor,
            "literal_start": match.start(),
            "source_text_sha256": original_text_sha,
            "context_start": lo,
            "context_end": hi,
            "context_sha256": _sha(local.encode("utf8")),
            "context_flag": flag,
            "review_status": "LITERAL_SIGNAL_NOT_LEGAL_INTERPRETATION",
        })
    return result


def source_bound_triage(root: Path, attachment_inventory: dict) -> dict:
    """Require exactly 50+25+21 source-matched, hash-verified attachments."""
    cases = attachment_inventory.get("cases", [])
    if len(cases) != 20 or attachment_inventory.get("source_shas_attested") != 96:
        raise ValueError("complete original EIS source inventory required")
    expected = {}
    for case in cases:
        for doc in case["documents"]:
            key = (case["registry_number"], doc["original_document_sha256"])
            if key in expected:
                raise ValueError("duplicate original source attachment")
            expected[key] = doc
    if len(expected) != 96:
        raise ValueError("expected 96 distinct original attachments")

    ai = root / "ai-expert-20261012"
    groups = (
        (ai / "competitive-prior50-original-text-20261014",
         "source-text50-private-receipt.json", _PRIOR50_SHA, 50,
         "OLDER_VERIFIED_TLS_RECHECK"),
        (ai / "competitive-25-original-text-20261014",
         "text-extraction-private-receipt.json", _FRESH25_SHA, 25,
         "NEWLY_RETRIEVED_OFFICIAL_SOURCE"),
    )
    verified_texts: dict[tuple[str, str], list[str]] = defaultdict(list)
    for directory, filename, digest, count, method in groups:
        for rec in _read_original_text_receipt(directory / filename, digest, count):
            if method == "OLDER_VERIFIED_TLS_RECHECK":
                number, original_sha = rec["registry_number"], rec["original_sha256"]
                name, text_name = rec["original_name"], rec["private_text_filename"]
                text_sha, chars, state = (rec["normalized_sha256"],
                                          rec["normalized_chars"], rec["text_state"])
            else:
                number, original_sha = rec["registry_number"], rec["origin_sha256"]
                name, text_name = rec["source_name"], rec["text_private_file"]
                text_sha, chars, state = (rec["text_sha256"],
                                          rec["text_chars"], rec["text_status"])
            key = number, original_sha
            doc = expected.get(key)
            if (not doc or doc["source_proof"] != method or doc["original_filename"] != name
                    or state != "TEXT_EXTRACTED" or verified_texts[key]):
                raise ValueError("text/notice identity, status or duplicate mismatch")
            _verify_text_location(directory, number, text_name, text_sha, chars)
            verified_texts[key].append((directory / number / text_name).read_text("utf8"))

    extra = ai / "positive-docs-recovery-20261012"
    receipt = pinned(extra / "official-21-attachments-receipt.json", PINS["official"])
    extraction = pinned(extra / "text-extraction-21-receipt.json", PINS["extract"])
    if len(receipt.get("results", [])) != 21 or len(extraction.get("text_units", [])) != 22:
        raise ValueError("new original attachment/text receipt incomplete")
    by_uid = {}
    for row in receipt["results"]:
        number, sha = row["reg_number"], row["sha256"]
        key = number, sha
        doc = expected.get(key)
        if (not doc or doc["source_proof"] != "ADDITIONAL_ORIGINAL_DOWNLOAD"
                or row["status"] != "OFFICIAL_BINARY_VERIFIED"):
            raise ValueError("additional original not in selected notice")
        orig = _trusted_private_file(extra, row["private_local_path"])
        if _sha(orig.read_bytes()) != sha or orig.stat().st_size != row["actual_bytes"]:
            raise ValueError("additional original binary differs from first-party receipt")
        uid = number, row["uid"]
        if uid in by_uid:
            raise ValueError("duplicate official source UID")
        by_uid[uid] = key
    for row in extraction["text_units"]:
        uid = row["reg_number"], row["source_uid"]
        key = by_uid.get(uid)
        if (key is None or row["outer_sha256"] != key[1]
                or row["text_status"] != "TEXT_EXTRACTED"):
            raise ValueError("extracted inner text cannot be traced to an original binary")
        p = _trusted_private_file(extra, row["private_text_path"])
        data = p.read_bytes()
        if _sha(data) != row["text_sha256"] or not data.decode("utf8").strip():
            raise ValueError("additional original document text is missing or tampered")
        verified_texts[key].append(data.decode("utf8"))

    if set(verified_texts) != set(expected) or sum(len(v) for v in verified_texts.values()) != 97:
        raise ValueError("not all 96 selected source attachments have an attested text")
    signals = []
    for (number, sha), texts in sorted(verified_texts.items()):
        doc = expected[number, sha]
        # Multiple text units can originate from one official ZIP attachment.
        for part, content in enumerate(texts, 1):
            for match in literal_candidates(content):
                signals.append({
                    "registry_number": number,
                    "original_filename": doc["original_filename"],
                    "original_binary_sha256": sha,
                    "original_notice_source_method": doc["source_proof"],
                    "text_part": part,
                    **match,
                    "expert_signed": False,
                    "bid_ready": False,
                })
    verified_examples = []
    for number, topic, quote in _VERIFIED_NONREQUIREMENT_SNIPPETS:
        matches = [
            record for record in signals
            if record["registry_number"] == number and record["review_topic"] == topic
            and record["context_flag"] == "NEGATION_CUE_NEAR_MENTION"
        ]
        if len(matches) != 1:
            raise ValueError("previously examined negative wording has changed")
        entry = matches[0]
        unit = verified_texts[(number, entry["original_binary_sha256"])][entry["text_part"] - 1]
        if quote not in unit or quote not in unit[
            entry["context_start"]:entry["context_end"]
        ]:
            raise ValueError("original context quotation no longer exactly matches source")
        verified_examples.append({
            "registry_number": number,
            "review_topic": topic,
            "archived_quote": quote,
            "archived_quote_sha256": _sha(quote.encode("utf8")),
            "original_filename": entry["original_filename"],
            "original_binary_sha256": entry["original_binary_sha256"],
            "source_locator": entry["source_locator"],
            "source_text_sha256": entry["source_text_sha256"],
            "legal_interpretation_signed": False,
            "current_eis_verified": False,
            "bid_ready": False,
        })
    per_case = Counter(x["registry_number"] for x in signals)
    context_per_case: dict[str, Counter[str]] = defaultdict(Counter)
    for signal in signals:
        context_per_case[signal["registry_number"]][signal["context_flag"]] += 1
    topics_by_case: dict[str, Counter[str]] = defaultdict(Counter)
    for signal in signals:
        topics_by_case[signal["registry_number"]][signal["review_topic"]] += 1
    case_summary = [
        {
            "registry_number": case["registry_number"],
            "source_documents_read": case["required_original_attachments"],
            "literal_topic_leads": per_case[case["registry_number"]],
            "negation_cue_leads": context_per_case[case["registry_number"]][
                "NEGATION_CUE_NEAR_MENTION"
            ],
            "heading_like_leads": context_per_case[case["registry_number"]][
                "POSSIBLE_HEADING_OR_TABLE_LABEL"
            ],
            "obligation_verb_leads": context_per_case[case["registry_number"]][
                "OBLIGATION_VERB_NEAR_MENTION"
            ],
            "top_review_topics": [
                name for name, _ in sorted(
                    topics_by_case[case["registry_number"]].items(),
                    key=lambda item: (-item[1], item[0]),
                )[:3]
            ],
            "expert_interpretation": "PENDING",
            "bid_ready": False,
        }
        for case in sorted(cases, key=lambda c: c["registry_number"])
    ]
    return {
        "scope": "ARCHIVED_96_SOURCE_LITERAL_TOPIC_TRIAGE_NOT_LEGAL_GOLD",
        "original_attachments_with_source_matched_text": len(verified_texts),
        "source_text_units_read": sum(len(v) for v in verified_texts.values()),
        "case_count": len(case_summary),
        "cases": case_summary,
        "source_bound_literal_leads": signals,
        "context_flag_totals": dict(sorted(Counter(
            signal["context_flag"] for signal in signals
        ).items())),
        "literal_scope": "FIRST_MENTION_OF_EIGHT_TOPICS_PER_SOURCE_TEXT_UNIT",
        "manually_rechecked_archival_nonrequirement_wording": verified_examples,
        "review_topic_categories": [name for name, _ in TOPICS],
        "human_signed_full_semantic_reviews": 0,
        "current_eis_revision_attested": False,
        "bid_ready": False,
        "limitations": (
            "Context flags are lexical cues only, NOT legal classifications. "
            "One first occurrence per topic per text unit; all other occurrences "
            "and operative document clauses are not exhaustively reviewed. "
            "Literal lexical signals can occur in a negation, example, heading, or "
            "inapplicable annex. Absence of a match does not prove absence of a duty. "
            "Original tables, scans, figures and legal applicability require human review."
        ),
    }
