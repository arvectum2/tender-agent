"""Build an offline, source-bound review packet for ChatGPT-in-chat via RDC.

No network, LLM calls, bidding, or automatic semantic/legal verdicts. The input
is a *local* model transcript plus a manifest of separately cached originals.
Only bounded excerpts are exported; entire source documents stay on the Mac.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_REG_NUMBER = re.compile(r"^[0-9]{19}$")
_RUN_ID = re.compile(r"^toa-run-[0-9]{10,16}-[0-9a-f]{4,24}$")
_SOURCE_FILE = re.compile(r"^file-[0-9]{2,4}-[a-zA-Z0-9_-]+\.txt$")
_MAX_CASES = 40
_MAX_CLAIMS = 64
_MAX_SOURCE_BYTES = 3_000_000


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_evidence(
    *,
    run_path: Path,
    source: str,
    expected_sha: str | None,
    quote: str,
) -> dict[str, Any]:
    if not _SOURCE_FILE.fullmatch(source):
        return {"status": "SOURCE_NAME_REJECTED"}
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        return {"status": "SOURCE_NOT_IN_MANIFEST"}
    path = run_path / "normalized" / source
    # Require the actual file, not a symlink that escapes the evidence directory.
    if path.is_symlink() or not path.is_file():
        return {"status": "ORIGINAL_UNAVAILABLE"}
    try:
        if path.stat().st_size > _MAX_SOURCE_BYTES:
            return {"status": "SOURCE_EXCEEDS_BOUNDS"}
        raw = path.read_bytes()
        digest = _sha256(raw)
        if digest != expected_sha:
            return {"status": "SOURCE_SHA256_MISMATCH", "actual_sha256": digest}
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        return {"status": "ORIGINAL_UNREADABLE"}
    if not quote or len(quote) > 800 or len(quote) < 12:
        return {"status": "QUOTE_INVALID", "source_sha256": digest}
    offsets = [m.start() for m in re.finditer(re.escape(quote), text)]
    if len(offsets) != 1:
        # Formatting-only matches need a separate expert check. Never promote
        # them to LITERAL_MATCH: these are not exact original offsets.
        whitespace_quote = " ".join(quote.split())
        whitespace_count = (
            " ".join(text.split()).count(whitespace_quote)
            if whitespace_quote and not offsets
            else 0
        )
        return {
            "status": (
                "QUOTE_FORMAT_VARIANT"
                if whitespace_count
                else "QUOTE_MISSING" if not offsets else "QUOTE_AMBIGUOUS"
            ),
            "occurrences": len(offsets) if offsets else whitespace_count,
            "source_sha256": digest,
            "semantic_review": "REQUIRES_CHATGPT_IN_CHAT",
            "legal_review": "UNKNOWN",
            "go_eligible": False,
        }
    offset = offsets[0]
    lo, hi = max(0, offset - 160), min(len(text), offset + len(quote) + 160)
    return {
        "status": "LITERAL_MATCH",
        "source_sha256": digest,
        "normalized_char_offset": offset,
        "normalized_char_end": offset + len(quote),
        "bounded_source_context": text[lo:hi],
        "context_offset": lo,
        "semantic_review": "REQUIRES_CHATGPT_IN_CHAT",
        "legal_review": "UNKNOWN",
        "go_eligible": False,
    }


def build_review_packet(
    transcript: dict[str, Any],
    manifest: list[dict[str, Any]],
    runs_root: Path,
) -> dict[str, Any]:
    """Return immutable factual evidence pointers, not an expert verdict."""
    cases = transcript.get("cases")
    if not isinstance(cases, list) or len(cases) > _MAX_CASES:
        raise ValueError("invalid or unbounded case collection")
    records = {
        row.get("reg_number"): row for row in manifest
        if isinstance(row, dict) and isinstance(row.get("reg_number"), str)
    }
    results = []
    for case in cases:
        number = case.get("reg_number") if isinstance(case, dict) else None
        claims = case.get("claims") if isinstance(case, dict) else None
        if (
            not isinstance(number, str)
            or not _REG_NUMBER.fullmatch(number)
            or not isinstance(claims, list)
            or len(claims) > _MAX_CLAIMS
        ):
            raise ValueError("invalid or unbounded case/claim data")
        record = records.get(number)
        run_id = record.get("run_id") if record else None
        valid_run = isinstance(run_id, str) and bool(_RUN_ID.fullmatch(run_id))
        manifest_sources = {
            row.get("source"): row.get("sha256_normalized_text")
            for row in record.get("source_evidence", [])
            if isinstance(row, dict)
        } if record else {}
        items = []
        for item in claims:
            source = item.get("source") if isinstance(item, dict) else None
            quote = item.get("quote") if isinstance(item, dict) else None
            interpretation = item.get("interpretation") if isinstance(item, dict) else None
            evidence = (
                _source_evidence(
                    run_path=runs_root / run_id,
                    source=source,
                    expected_sha=manifest_sources.get(source),
                    quote=quote,
                )
                if valid_run and isinstance(source, str) and isinstance(quote, str)
                else {"status": "SOURCE_IDENTITY_UNAVAILABLE"}
            )
            items.append({
                "source": source if isinstance(source, str) else None,
                "interpretation": interpretation[:1200] if isinstance(interpretation, str) else None,
                "quote": quote[:800] if isinstance(quote, str) else None,
                "evidence": evidence,
            })
        results.append({
            "reg_number": number,
            "run_id": run_id if valid_run else None,
            "source_status": "MANIFEST_FOUND" if valid_run else "SOURCE_IDENTITY_UNAVAILABLE",
            "claims": items,
        })
    return {
        "schema_version": 1,
        "mode": "OFFLINE_LOCAL_LLM_TO_CHATGPT_RDC",
        "semantic_review": "NOT_PERFORMED_BY_THIS_TOOL",
        "owner_business_decision": "DEFER",
        "go_eligible": False,
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path.cwd().resolve()):
        raise SystemExit("Review output must be outside the current repository/worktree")
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    packet = build_review_packet(transcript, manifest, args.runs_root)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote local expert packet for {len(packet['cases'])} cases (no network)")


if __name__ == "__main__":
    main()
