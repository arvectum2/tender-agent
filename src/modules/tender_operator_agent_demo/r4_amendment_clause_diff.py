"""Case-independent, non-decisional changed-attachment text comparison.

Extracted original text is only a retrieval aid, not legally complete.
Never infer requirements, bidder eligibility, a source version or GO from a
lexical match or this comparison's text similarity.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from difflib import SequenceMatcher

from src.modules.tender_operator_agent_demo.r4_material_condition_triage import TOPICS

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PAR = re.compile(r"^(PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+):\s*")
_PAGE = re.compile(r"^(?:\[Page (\d+)\]|PDF PAGE (\d+))$")
_PATTERNS = tuple((topic, re.compile(pattern, re.IGNORECASE)) for topic, pattern in TOPICS)
_TOC = re.compile(r"\.{4,}\s*\d+\s*$")


def normalized_source_lines(text: str) -> list[dict[str, str]]:
    """Keep independent source locations while reducing extractor prefixes."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("No independently extracted original source text")
    out = []
    page, locator = "unknown", "unknown"
    for line_no, row in enumerate(text.splitlines(), 1):
        stripped = row.strip()
        if not stripped or stripped.startswith("NESTED "):
            continue
        page_match = _PAGE.fullmatch(stripped)
        if page_match:
            page = next(value for value in page_match.groups() if value)
            continue
        paragraph_match = _PAR.match(stripped)
        if paragraph_match:
            locator = paragraph_match.group(1)
            stripped = stripped[paragraph_match.end():]
        else:
            locator = f"PAGE-{page} LINE-{line_no}" if page != "unknown" else f"LINE-{line_no}"
        clean = " ".join(stripped.split())
        if not clean:
            continue
        out.append({"text": clean, "locator": locator})
    if not out:
        raise ValueError("Empty normalized original source lines")
    return out


def audit_changed_material(
    old_text: str,
    current_text: str,
    *,
    previous_original_sha256: str,
    current_original_sha256: str,
    max_leads_per_topic: int = 4,
) -> dict:
    """Return anchored *review questions*, never legal assertions.

    Similarity is not completeness; PDF extraction may reorder source lines.
    Lexical matches in deleted or added lines do not prove new duties.
    """
    if not all(isinstance(v, str) and _SHA.fullmatch(v) for v in (
        previous_original_sha256, current_original_sha256
    )):
        raise ValueError("Original binary SHA proof absent")
    if not 1 <= max_leads_per_topic <= 20:
        raise ValueError("Bounded topical source lead limit expected")
    prior = normalized_source_lines(old_text)
    latest = normalized_source_lines(current_text)
    before = [v["text"] for v in prior]
    after = [v["text"] for v in latest]
    alignment = SequenceMatcher(None, before, after, autojunk=False)
    changed_previous = set()
    changed_current = set()
    counts: Counter[str] = Counter()
    for action, i1, i2, j1, j2 in alignment.get_opcodes():
        if action == "equal":
            continue
        counts[action] += 1
        changed_previous.update(range(i1, i2))
        changed_current.update(range(j1, j2))
    old_topic_hits: Counter[str] = Counter()
    new_topic_hits: Counter[str] = Counter()
    topical_candidates = []
    for topic, compiled in _PATTERNS:
        old_topic_hits[topic] = sum(bool(compiled.search(v["text"])) for v in prior)
        new_topic_hits[topic] = sum(bool(compiled.search(v["text"])) for v in latest)
        entries = []
        for index in sorted(changed_current):
            line = latest[index]
            match = compiled.search(line["text"])
            if match and not _TOC.search(line["text"]):
                entries.append({
                    "source_locator": line["locator"],
                    "source_line_sha256": hashlib.sha256(line["text"].encode("utf8")).hexdigest(),
                    "matched_literal": match.group(0),
                    "short_source_excerpt": line["text"][:320],
                    "interpretation_status": "UNVERIFIED_LEXICAL_LEAD_REVIEW_REQUIRED",
                })
            if len(entries) >= max_leads_per_topic:
                break
        if entries:
            topical_candidates.append({
                "topic": topic,
                "changed_current_lines_with_topic": sum(
                    bool(compiled.search(latest[i]["text"])) and not _TOC.search(latest[i]["text"])
                    for i in changed_current
                ),
                "table_of_contents_hits_excluded": sum(
                    bool(compiled.search(latest[i]["text"])) and bool(_TOC.search(latest[i]["text"]))
                    for i in changed_current
                ),
                "bounded_source_leads": entries,
            })
    return {
        "previous_original_binary_sha256": previous_original_sha256,
        "current_original_binary_sha256": current_original_sha256,
        "previous_extracted_text_sha256": hashlib.sha256(old_text.encode("utf8")).hexdigest(),
        "current_extracted_text_sha256": hashlib.sha256(current_text.encode("utf8")).hexdigest(),
        "old_text_lines": len(prior),
        "current_text_lines": len(latest),
        "textual_sequence_similarity": round(alignment.ratio(), 4),
        "diff_blocks_by_kind": dict(sorted(counts.items())),
        "unmatched_old_lines": len(changed_previous),
        "unmatched_current_lines": len(changed_current),
        "topic_line_counts_old": dict(old_topic_hits),
        "topic_line_counts_current": dict(new_topic_hits),
        "changed_new_text_topical_leads": topical_candidates,
        "legal_meaning_verified": False,
        "independent_legal_expert_signed": False,
        "source_text_extraction_complete": False,
        "scope_notice": (
            "Case-independent text-layer diff only: extractor/format/layout "
            "differences can produce misleading changes. New textual matches "
            "are questions for human review, not proven duties or bid GO."
        ),
    }
