"""Seed ChatGPT-via-ARC review queue from already downloaded official documents.

Read-only to original source directories. Never claim that downloaded files are
signed contracts or representative of the whole procurement market.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .pq_review_queue import enqueue

REGISTRY = re.compile(r"^[0-9]{11}$|^[0-9]{19,20}$")
ALLOWED = {".pdf", ".docx", ".xlsx", ".txt"}


def seed(*, sources: Path, ontology: Path, queue_dir: Path,
         max_cases: int = 20, max_files: int = 8) -> dict:
    if sources.is_symlink() or not sources.is_dir() or not 1 <= max_cases <= 200:
        raise ValueError("Invalid source root or case budget")
    result = {"source_root": str(sources), "created": [], "existing": [],
              "skipped": [], "errors": []}
    for directory in sorted(sources.iterdir()):
        if len(result["created"]) + len(result["existing"]) >= max_cases:
            break
        if not directory.is_dir() or directory.is_symlink() or not REGISTRY.fullmatch(directory.name):
            continue
        files = [p for p in directory.iterdir()
                 if p.is_file() and not p.is_symlink() and p.suffix.lower() in ALLOWED]
        if not files:
            result["skipped"].append({"registry": directory.name, "reason": "no_supported_originals"})
            continue
        try:
            before = set(queue_dir.glob(f"{directory.name}-*.json"))
            item = enqueue(source_dir=directory, ontology=ontology,
                           registry_number=directory.name, queue_dir=queue_dir,
                           max_files=max_files)
            key = "existing" if queue_dir / (item["id"] + ".json") in before else "created"
            result[key].append({"registry": directory.name, "id": item["id"],
                                "documents": len(item["packet"]["documents"])})
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            result["errors"].append({"registry": directory.name,
                                     "error_type": type(exc).__name__})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(seed(sources=args.sources, ontology=args.ontology,
                          queue_dir=args.queue_dir, max_cases=args.max_cases),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
