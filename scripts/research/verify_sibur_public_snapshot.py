"""Verify archived SIBUR first-party pages and normalize their historical rows.

Read-only offline input: no source fetching, DB calls, file changes or imports.
An exact full-page replay is required; partial snapshots fail closed.
"""

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from src.modules.tender_connectors.sibur.parser import MAX_RESPONSE, parse_page

MAX_PAGES = 40
META_LIMIT = 8_000_000
CURRENT_ONLY_FIELDS = frozenset({"documentation_urls", "unverified_document_links"})


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _read_exact(root: Path, filename: str, maximum: int) -> bytes:
    path = root / filename
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("missing, linked or oversized original snapshot member")
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError("oversized original snapshot member")
    return raw


def _json(root: Path, filename: str):
    return json.loads(_read_exact(root, filename, META_LIMIT), object_pairs_hook=_reject_duplicate_keys)


def replay_verified_originals(root: Path) -> list[dict]:
    """Return rows freshly parsed from SHA-verified original pages, never saved normalized guesses."""
    if not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise ValueError("unsafe snapshot root")
    receipt = _json(root, "receipts.json")
    saved = _json(root, "normalized.json")
    if (not isinstance(receipt, dict) or receipt.get("source") != "sibur_public"
            or receipt.get("verification") != "PUBLIC_LIST_SNAPSHOT_NOT_HISTORICAL_COVERAGE"
            or receipt.get("page_count_stable") is not True
            or receipt.get("errors") != []):
        raise ValueError("unverified or partial receipt")
    total = receipt.get("announced_pages")
    if (type(total) is not int or not 1 <= total <= MAX_PAGES
            or receipt.get("validated_pages") != total
            or not isinstance(receipt.get("pages"), list)
            or len(receipt["pages"]) != total):
        raise ValueError("incomplete source pagination")
    groups = defaultdict(list)
    seen = 0
    for number, member in enumerate(receipt["pages"], 1):
        if not isinstance(member, dict) or member.get("page") != number or member.get("last_page") != total:
            raise ValueError("wrong page identity")
        name = f"page-{number:03d}.json"
        raw = _read_exact(root, name, MAX_RESPONSE)
        expected_sha = member.get("sha256")
        if (not isinstance(expected_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None
                or type(member.get("bytes")) is not int
                or len(raw) != member["bytes"]
                or hashlib.sha256(raw).hexdigest() != expected_sha):
            raise ValueError("unverified first-party raw page digest")
        page = parse_page(raw, number)
        count = member.get("rows", member.get("records"))
        if (page.sha256 != expected_sha or page.last_page != total
                or type(count) is not int or count != len(page.records)):
            raise ValueError("original page parsing differs from receipt")
        seen += len(page.records)
        for row in page.records:
            groups[row["external_id"]].append(row)
    if (type(receipt.get("raw_rows")) is not int or seen != receipt["raw_rows"]
            or type(receipt.get("unique_ids")) is not int
            or len(groups) != receipt["unique_ids"]):
        raise ValueError("source-reported count does not equal parsed rows")
    if not isinstance(saved, list) or len(saved) != len(groups):
        raise ValueError("historical normalized membership mismatch")
    rebuilt = [{"external_id": k, "observations": v} for k, v in groups.items()]
    for old, current in zip(saved, rebuilt, strict=True):
        if (not isinstance(old, dict) or set(old) != {"external_id", "observations"}
                or old["external_id"] != current["external_id"]
                or not isinstance(old["observations"], list)
                or len(old["observations"]) != len(current["observations"])):
            raise ValueError("historical group identity or row count mismatch")
        for old_row, new_row in zip(old["observations"], current["observations"], strict=True):
            if not isinstance(old_row, dict):
                raise TypeError("historical row invalid")
            fields = set(new_row)
            if (set(old_row) != fields and set(old_row) != fields - CURRENT_ONLY_FIELDS):
                raise ValueError("unreviewed historical row schema")
            if any(old_row[key] != new_row[key] for key in old_row):
                raise ValueError("historical original row content changed")
    return rebuilt
