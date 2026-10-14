"""Evidence proof contract for original-source tender claims.

A source citation proves exact extracted text only. Typed EIS XML values can be
compared mechanically against explicitly declared claims, but are historical
until the official EIS revision is independently attested. Page/sheet anchors
are NEVER inferred from normalized Unicode character offsets.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_PROOFABLE_XML_FIELDS = frozenset({"nmck", "submission_deadline", "procurement_subject"})
_SHA_PATTERN = re.compile(r"[a-f0-9]{64}")
_EXACT_SPAN_STATUS = "EXACT_NORMALIZED_SOURCE_TEXT"
_UNLOCATED = "SOURCE_SPAN_UNVERIFIED"
_NO_PAGE = "PAGE_OR_CELL_NOT_ATTESTED"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trusted_index(research: dict[str, Any]) -> dict[str, dict[str, Any]]:
    good = [
        row for row in (research.get("documents") or [])
        if row.get("status") == "EXTRACTED" and
        _SHA_PATTERN.fullmatch(str(row.get("text_sha256") or ""))
    ]
    keys = [str(row.get("file_id") or "").casefold() for row in good]
    return {k: row for k, row in zip(keys, good) if k and keys.count(k) == 1}


def _source_document(documents: list[Any], file_id: str, expected_sha: str) -> str | None:
    originals = [
        getattr(d, "text", None)
        for d in documents if str(getattr(d, "file_id", "") or "").casefold() == file_id.casefold()
    ]
    if len(originals) != 1 or not isinstance(originals[0], str):
        return None
    return originals[0] if _sha(originals[0]) == expected_sha else None


def bind_source_span(
    documents: list[Any],
    research: dict[str, Any],
    *,
    file_id: str,
    start: int,
    end: int,
    quote: str,
    expected_text_sha256: str,
    physical_locator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind a quote or fail closed. Physical locator needs a checked mapping.

    A claimed page/worksheet is never treated as real without a separately
    supplied normalized-to-original mapping with identical source SHA and
    a mapping span containing this specific excerpt.
    """
    result: dict[str, Any] = {
        "file_id": file_id, "start": start, "end": end,
        "source_sha256": expected_text_sha256,
        "status": _UNLOCATED, "physical_locator_status": _NO_PAGE,
        "physical_locator": None,
        "semantic_verification": "NOT_PERFORMED",
        "requires_human_review": True,
    }
    indexed = _trusted_index(research).get(file_id.casefold())
    if indexed is None or indexed["text_sha256"] != expected_text_sha256:
        return result
    text = _source_document(documents, file_id, expected_text_sha256)
    if text is None or not isinstance(start, int) or not isinstance(end, int):
        return result
    if start < 0 or end <= start or end > len(text) or text[start:end] != quote:
        return result
    result["status"] = _EXACT_SPAN_STATUS
    result["quote_sha256"] = _sha(quote)
    result["quote"] = quote
    result["source_ref"] = f"normalized:{file_id}:{start}-{end}"
    # A page/cell can only be accepted with proof of an externally extracted
    # mapping. Do not believe unchecked human/LLM "page 12" labels.
    location = physical_locator if isinstance(physical_locator, dict) else {}
    mapping = location.get("normalized_span_map")
    if isinstance(mapping, dict) and (
        mapping.get("source_sha256") == expected_text_sha256
        and mapping.get("file_id", "").casefold() == file_id.casefold()
        and isinstance(mapping.get("start"), int)
        and isinstance(mapping.get("end"), int)
        and mapping["start"] <= start < end <= mapping["end"]
        and location.get("extraction_attested") is True
    ):
        kind = location.get("kind")
        label = location.get("label")
        if kind in {"pdf_page", "docx_page", "spreadsheet_cell"} and isinstance(label, str) and label.strip():
            result["physical_locator_status"] = "EXPLICIT_SOURCE_MAPPING_REVIEW"
            result["physical_locator"] = {"kind": kind, "label": label.strip()}
    return result


def _normalized_value(kind: str, value: Any) -> str | None:
    if kind == "nmck":
        if isinstance(value, bool) or value is None:
            return None
        try:
            raw = str(value).strip().replace("\u00a0", "").replace(" ", "")
            has_group_separators = (
                ("," in raw and "." in raw and raw.index(",") < raw.rindex("."))
                or (raw.count(",") > 1 and "." not in raw)
            )
            raw = raw.replace(",", "" if has_group_separators else ".")
            number = Decimal(raw)
            if not number.is_finite() or number < 0:
                return None
            return str(number.normalize())
        except (InvalidOperation, ValueError):
            return None
    if kind == "submission_deadline":
        raw = str(value or "").strip()
        # Accept aware ISO 8601, and Russian EIS parser strings with offset.
        raw = raw.replace("Z", "+00:00")
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}\s*[+-]\d{2}:\d{2}", raw):
            date, clock, tz = raw.split()
            raw = f"{date[6:10]}-{date[3:5]}-{date[:2]}T{clock}{tz}"
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed.isoformat() if parsed.tzinfo is not None else None
        except ValueError:
            return None
    if kind == "procurement_subject":
        return re.sub(r"\s+", " ", str(value or "")).strip().casefold() or None
    return None


def check_typed_original_facts(
    research: dict[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare *typed* assertions to unique registry-safe historical EIS facts.

    A value match means only 'matches this archived source', never legal truth,
    live submission status or bidder eligibility. Other claim types abstain.
    """
    trusted = _trusted_index(research)
    accepted = [
        f for f in research.get("structured_notice_facts", [])
        if str(f.get("file_id") or "").casefold() in trusted
        and trusted[str(f["file_id"]).casefold()]["text_sha256"] == f.get("source_sha256")
        and f.get("source_status") == "ORIGINAL_XML_EXTRACTED_NOT_CURRENT_ATTESTED"
    ]
    notices = {str(f.get("file_id") or "").casefold() for f in accepted}
    edition_conflict = (
        bool(research.get("multiple_notices_require_revision_resolution"))
        or len(notices) > 1
        or research.get("source_status") == "INCOMPLETE"
    )
    results = []
    for claim in claims[:100]:
        kind = str(claim.get("field") or "")
        actual = _normalized_value(kind, claim.get("value"))
        candidates = [
            f for f in accepted if f.get("field") == kind
        ] if kind in _PROOFABLE_XML_FIELDS else []
        if edition_conflict:
            verdict = "SOURCE_CORPUS_OR_REVISION_UNRESOLVED"
        elif not candidates or actual is None:
            verdict = "UNKNOWN_NOT_ATTESTED"
        else:
            ref_values = {_normalized_value(kind, f.get("value")) for f in candidates}
            if len(ref_values) != 1 or None in ref_values:
                verdict = "CONFLICTING_SOURCE_VALUES"
            elif actual in ref_values:
                verdict = "MATCHES_HISTORICAL_EIS_SOURCE"
            else:
                verdict = "CONTRADICTED_BY_HISTORICAL_EIS_SOURCE"
        results.append({
            "field": kind,
            "claim_value": claim.get("value"),
            "status": verdict,
            "source_refs": [
                {"file_id": f["file_id"], "sha256": f["source_sha256"],
                 "registry_number": f["procurement_number"], "source_value": f["value"]}
                for f in candidates[:4]
            ],
            "current_official_revision_attested": False,
            "semantic_entailment_verified": False,
            "requires_human_review": True,
        })
    return {
        "status": "HISTORICAL_ONLY_HUMAN_REVIEW",
        "claims": results,
        "source_corruption_or_revision_conflict": edition_conflict,
        "bid_ready": False,
    }


def extract_model_eis_summary_claims(requirements: dict[str, Any]) -> list[dict[str, Any]]:
    """Strictly extract explicit labelled numbers/dates, not free prose guesses.

    An unrecognised label is NOT silently assigned to an EIS field, and a
    missed parser match is exposed separately as an unanswered source field.
    """
    summary = str(requirements.get("tender_summary") or "")
    claims: list[dict[str, Any]] = []
    price = re.search(
        r"(?:НМЦК|NMCK)\s*[:=–-]\s*"
        r"(?P<value>\d[\d,.\s]*\d|\d)\s*(?:RUB|₽|руб(?:лей)?)",
        summary, re.IGNORECASE,
    )
    if price:
        claims.append({"field": "nmck", "value": price.group("value").strip()})
    deadline = re.search(
        r"(?:submission\s+deadline|срок\s+подачи\s+заявок)\s*[:=–-]\s*"
        r"(?P<value>(?:\d{4}-\d{2}-\d{2}T|\d{2}\.\d{2}\.\d{4}\s+)"
        r"\d{2}:\d{2}(?::\d{2})?\s*[+-]\d{2}:\d{2})",
        summary, re.IGNORECASE,
    )
    if deadline:
        claims.append({"field": "submission_deadline", "value": deadline.group("value").strip()})
    return claims


def audit_model_eis_summary(
    research: dict[str, Any],
    requirements: dict[str, Any],
) -> dict[str, Any]:
    claims = extract_model_eis_summary_claims(requirements)
    checked = check_typed_original_facts(research, claims)
    available = {
        str(f.get("field")) for f in research.get("structured_notice_facts", [])
        if f.get("field") in {"nmck", "submission_deadline"}
    }
    asserted = {c["field"] for c in claims}
    checked["unmentioned_archived_eis_fields"] = sorted(available - asserted)
    checked["explicit_assertions_count"] = len(claims)
    checked["contradictions_count"] = sum(
        c["status"] == "CONTRADICTED_BY_HISTORICAL_EIS_SOURCE"
        for c in checked["claims"]
    )
    checked["claim_semantics_verified"] = False
    return checked
