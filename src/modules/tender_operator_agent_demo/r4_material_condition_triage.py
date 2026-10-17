"""Source-attested, non-decisional material-condition leads across all 96 originals.

Only literal topical signals, not legal duties/eligibility/GO. Read-only private
text inputs have pinned receipts and are matched to the selected notice edition.
Public output never contains filesystem paths, UIDs or surrounding source text.
"""
from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
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
from src.modules.tender_operator_agent_demo.r4_cross_document_scope_review import (
    verify_archival_scope_contrasts,
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


# Independently checked source meaning for five PRECISE archival clauses.
# Not a general legal rule, qualifications registry or participant GO.
_LICENSE_SOURCE_ROLE_CASES = (
    (
        "0151600003226000011",
        "ISSUING_BANK_LICENSE_NOT_PARTICIPANT_LICENSE",
        "у банка, предоставившего независимую гарантию",
        "Условие об отзыве банковской лицензии у банка-гаранта",
    ),
    (
        "0348100024426000039",
        "ISSUING_BANK_LICENSE_NOT_PARTICIPANT_LICENSE",
        "у банка, предоставившего независимую гарантию",
        "Условие об отзыве банковской лицензии у банка-гаранта",
    ),
    (
        "0372200172326000015",
        "ISSUING_BANK_LICENSE_NOT_PARTICIPANT_LICENSE",
        "у банка, предоставившего независимую гарантию",
        "Условие об отзыве банковской лицензии у банка-гаранта",
    ),
    (
        "0895100000126000897",
        "DELIVERED_SOFTWARE_LICENSE_TERMS_NOT_PARTICIPANT_LICENSE",
        "Лицензии на такие программные продукты не должны",
        "Ограничения условий лицензий на программные продукты",
    ),
    (
        "0349100009326000005",
        "CONTRACTOR_LICENSE_WORDING_REQUIRES_LEGAL_REVIEW",
        "Исполнитель должен иметь лицензию на телематические услуги связи",
        "Формулировка проекта контракта о лицензии исполнителя",
    ),
)

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



def all_topic_occurrences(text: str) -> list[dict]:
    """Scan every occurrence of the same eight keywords, not just their first hit.

    The exhaustive claim applies ONLY to these fixed patterns and current
    normalized text, never to completeness of contract obligations or OCR.
    """
    original_hash = _sha(text.encode("utf8"))
    anchors = [(m.start(), m.group(0)) for m in _LOCATOR.finditer(text)]
    anchor_positions = [a[0] for a in anchors]
    newline_positions = [m.start() for m in re.finditer("\n", text)]
    matches = []
    for title, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            anchor_ix = bisect_right(anchor_positions, match.start()) - 1
            line_ix = bisect_right(newline_positions, match.start())
            anchor = (anchors[anchor_ix][1] if anchor_ix >= 0
                      else f"Строка {line_ix + 1}")
            local, lo, hi, flag = _local_context(text, match.start(), match.end())
            matches.append({
                "review_topic": title,
                "literal_text": match.group(0),
                "literal_start": match.start(),
                "source_locator": anchor,
                "source_text_sha256": original_hash,
                "context_start": lo,
                "context_end": hi,
                "context_sha256": _sha(local.encode("utf8")),
                "context_flag": flag,
                "review_status": "LEXICAL_HIT_NOT_LEGAL_OBLIGATION",
            })
    return sorted(matches, key=lambda v: (v["literal_start"], v["review_topic"]))

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
    all_mention_total = 0
    occurrence_summary = []
    second_hit_source_leads = []
    for (number, sha), texts in sorted(verified_texts.items()):
        doc = expected[number, sha]
        # Multiple text units can originate from one official ZIP attachment.
        for part, content in enumerate(texts, 1):
            first = literal_candidates(content)
            all_hits = all_topic_occurrences(content)
            if len(all_hits) < len(first):
                raise ValueError("all-occurrence scan lost first topical hits")
            all_mention_total += len(all_hits)
            counts = Counter(v["review_topic"] for v in all_hits)
            occurrence_summary.append({
                "registry_number": number,
                "original_filename": doc["original_filename"],
                "original_binary_sha256": sha,
                "original_notice_source_method": doc["source_proof"],
                "text_part": part,
                "first_topic_leads": len(first),
                "all_topic_occurrences": len(all_hits),
                "topic_occurrences": dict(sorted(counts.items())),
                "human_approved": False,
            })
            for match in first:
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
            # The previous report exposed only the FIRST hit per topic/source.
            # Independently pin the next occurrence (if any), showing the
            # reviewer an exact unexamined source point rather than claiming
            # all later contract clauses have been legally interpreted.
            for topic in counts:
                other = [v for v in all_hits if v["review_topic"] == topic]
                if len(other) < 2:
                    continue
                second = other[1]
                second_hit_source_leads.append({
                    "registry_number": number,
                    "original_filename": doc["original_filename"],
                    "original_binary_sha256": sha,
                    "text_part": part,
                    "review_topic": topic,
                    "literal_text": second["literal_text"],
                    "source_locator": second["source_locator"],
                    "literal_start": second["literal_start"],
                    "source_text_sha256": second["source_text_sha256"],
                    "context_sha256": second["context_sha256"],
                    "context_flag": second["context_flag"],
                    "review_status": "ADDITIONAL_OCCURRENCE_FOR_EXPERT_NOT_LEGAL_GOLD",
                    "human_signed": False,
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
    # At least one additional original locator per procurement, deliberately
    # selected outside the earlier first-hit-only sample. Filename ranking is
    # a navigation convenience, never a document type or legal interpretation.
    review_priority = {
        "Лицензирование/квалификация": 0,
        "Права на ПО и результаты": 1,
        "Персональные данные и ИБ": 2,
        "Гарантийные обязательства": 3,
        "Приёмка результата": 4,
        "Обеспечение заявки/контракта": 5,
        "Сроки исполнения": 6,
        "Оплата и аванс": 7,
    }

    def _example_rank(v: dict) -> tuple:
        name = v["original_filename"].lower()
        file_kind = (
            0 if "контракт" in name or "договор" in name or name == "пк.docx"
            else 1 if "описани" in name or "техническ" in name
            or "тз " in name or name == "ооз.docx"
            else 2 if "требован" in name or "заявк" in name
            else 3
        )
        context_kind = {
            "OBLIGATION_VERB_NEAR_MENTION": 0,
            "NEGATION_CUE_NEAR_MENTION": 1,
            "CONTEXT_UNCERTAIN": 2,
            "POSSIBLE_HEADING_OR_TABLE_LABEL": 3,
        }
        return (
            file_kind, context_kind.get(v["context_flag"], 4),
            review_priority[v["review_topic"]],
            v["original_filename"], v["literal_start"],
        )

    review_examples = []
    for case in sorted(cases, key=lambda v: v["registry_number"]):
        n = case["registry_number"]
        candidates = [v for v in second_hit_source_leads if v["registry_number"] == n]
        if not candidates:
            raise ValueError("no further original source condition located for procurement")
        selected = min(candidates, key=_example_rank)
        review_examples.append({
            **selected,
            "review_purpose": "ADDITIONAL_SOURCE_LOCATOR_NOT_LEGAL_GOLD",
            "bid_ready": False,
        })
    clarified_roles = []
    for number, role, exact_words, customer_question in _LICENSE_SOURCE_ROLE_CASES:
        candidates = [
            item for item in review_examples
            if item["registry_number"] == number
            and item["review_topic"] == "Лицензирование/квалификация"
        ]
        if len(candidates) != 1:
            raise ValueError("pinned extra source licence locator changed")
        example = candidates[0]
        units = verified_texts[(number, example["original_binary_sha256"])]
        if len(units) < example["text_part"]:
            raise ValueError("source text part missing from verified original")
        text = units[example["text_part"] - 1]
        position = example["literal_start"]
        context = text[max(0, position - 350):position + 350]
        if exact_words not in context:
            raise ValueError("literal licensing role cannot be checked in original context")
        clarified_roles.append({
            "registry_number": number,
            "source_role": role,
            "original_filename": example["original_filename"],
            "original_binary_sha256": example["original_binary_sha256"],
            "source_text_sha256": example["source_text_sha256"],
            "source_locator": example["source_locator"],
            "exact_original_words": exact_words,
            "exact_words_sha256": _sha(exact_words.encode("utf8")),
            "source_question": customer_question,
            "participant_eligibility_approved": False,
            "expert_signed": False,
            "bid_ready": False,
        })
    per_case = Counter(x["registry_number"] for x in signals)
    all_by_case = Counter()
    source_spans_by_case = Counter()
    for unit in occurrence_summary:
        all_by_case[unit["registry_number"]] += unit["all_topic_occurrences"]
        source_spans_by_case[unit["registry_number"]] += (
            unit["all_topic_occurrences"] - unit["first_topic_leads"]
        )
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
            "all_pattern_occurrences": all_by_case[case["registry_number"]],
            "previously_unreported_additional_occurrences": source_spans_by_case[
                case["registry_number"]
            ],
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
        "cross_document_original_scope_review": verify_archival_scope_contrasts(
            verified_texts, expected
        ),
        "source_bound_literal_leads": signals,
        "all_topic_mentions_scan": {
            "scope": "ALL_MATCHES_OF_EIGHT_FIXED_PATTERNS_IN_97_TEXT_UNITS_NOT_ALL_LEGAL_TERMS",
            "text_units": len(occurrence_summary),
            "original_attachments": len(verified_texts),
            "total_pattern_occurrences": all_mention_total,
            "first_only_prior_coverage": len(signals),
            "additional_pattern_occurrences": all_mention_total - len(signals),
            "unit_counts": occurrence_summary,
            "second_source_hit_per_topic": second_hit_source_leads,
            "one_additional_original_locator_per_case": review_examples,
            "license_context_role_clarifications": clarified_roles,
            "human_signed_legal_interpretation": 0,
            "bid_ready": False,
        },
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
