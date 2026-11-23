"""Read-only full historic SIBUR archive page/receipt inventory, not a live source crawler."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from src.modules.tender_connectors.sibur.archive_parser import (
    CATEGORIES,
    replay_archived_page,
)


def audit_corpus(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise ValueError("unsafe original archive root")
    items = []
    total_pages = total_rows = 0
    for category in CATEGORIES:
        folder = root / "categories" / category
        if category == "999_19":
            folder = root / "support-services-20261115" / category
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("missing category original evidence")
        head = replay_archived_page(folder, category, 1)
        expected = head.last_page
        receipt_page_set = {
            int(e.name[1:6]) for e in os.scandir(folder)
            if re.fullmatch(r"p\d{5}\.json", e.name)
        }
        if receipt_page_set != set(range(1, expected + 1)):
            raise ValueError("archive source page membership incomplete or extra")
        mismatched_pagination = []
        invalid_original_pages = []
        invalid_count = 0
        rows = 0
        member_hash = hashlib.sha256()
        for number in range(1, expected + 1):
            try:
                page = replay_archived_page(folder, category, number)
                if page.last_page != expected:
                    mismatched_pagination.append(number)
                member_hash.update(category.encode() + b":" + str(number).encode() + b":" + page.sha256.encode() + b"\n")
                rows += len(page.records)
            except (ValueError, TypeError, OSError) as exc:
                invalid_count += 1
                if len(invalid_original_pages) < 10:
                    invalid_original_pages.append({"page": number, "error": type(exc).__name__})
        items.append({
            "category": category,
            "source_advertised_page_count_at_first_page": expected,
            "receipt_page_count": len(receipt_page_set),
            "sha_pinned_pages_verified": expected - invalid_count,
            "rows_in_replayed_pages": rows,
            "changed_pagination_count": len(mismatched_pagination),
            "invalid_original_page_count": invalid_count,
            "changed_pagination_first_pages": mismatched_pagination[:5],
            "invalid_original_page_sample": invalid_original_pages,
            "member_aggregate_sha256": member_hash.hexdigest(),
        })
        total_pages += expected - invalid_count
        total_rows += rows
        print("VERIFIED_CATEGORY", category, "pages", expected - invalid_count,
              "of", expected, "rows", rows, "pagination_changed", len(mismatched_pagination),
              "page_errors", invalid_count, flush=True)
    passed = all(not c["changed_pagination_count"] and not c["invalid_original_page_count"]
                 for c in items)
    return {
        "status": "pass_historical_source_window" if passed else "needs_review",
        "source": "sibur_public_archived_categories",
        "source_categories": len(items),
        "verified_original_page_count": total_pages,
        "replayed_source_rows": total_rows,
        "category_receipts": items,
        "no_network_requests": True,
        "no_database_mutations": True,
        "current_2026_nov21_status_verified": False,
        "future_source_admission_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    result = audit_corpus(parser.parse_args().root)
    print("AUDIT_SUMMARY", json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    if result["status"] != "pass_historical_source_window":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
