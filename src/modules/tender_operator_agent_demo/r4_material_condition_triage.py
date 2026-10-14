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


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def literal_candidates(text: str) -> list[dict]:
    """One shortest locator per topic for this source; no fabricated interpretation."""
    result = []
    for title, pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        locators = list(re.finditer(r"PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+", text[:match.start()]))
        anchor = (locators[-1].group(0) if locators
                  else f"Строка {text.count(chr(10), 0, match.start()) + 1}")
        result.append({
            "review_topic": title,
            "literal_text": match.group(0),
            "source_locator": anchor,
            "literal_start": match.start(),
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
    per_case = Counter(x["registry_number"] for x in signals)
    topics_by_case: dict[str, Counter[str]] = defaultdict(Counter)
    for signal in signals:
        topics_by_case[signal["registry_number"]][signal["review_topic"]] += 1
    case_summary = [
        {
            "registry_number": case["registry_number"],
            "source_documents_read": case["required_original_attachments"],
            "literal_topic_leads": per_case[case["registry_number"]],
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
        "review_topic_categories": [name for name, _ in TOPICS],
        "human_signed_full_semantic_reviews": 0,
        "current_eis_revision_attested": False,
        "bid_ready": False,
        "limitations": (
            "Literal lexical signals can occur in a negation, example, heading, or "
            "inapplicable annex. Absence of a match does not prove absence of a duty. "
            "Original tables, scans, figures and legal applicability require human review."
        ),
    }
