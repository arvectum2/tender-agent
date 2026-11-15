"""Replay completed archive partitions; retain all duplicate and invalid observations privately."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.research.capture_gpb_history_partitions import (
    archive_rows,
    inspect,
    source_url,
)
from scripts.research.import_gpb_geh_snapshots import normalize


def prepare(root, months):
    state = json.loads((root / "state.json").read_text())
    accepted, review, manifests = [], [], []
    seen = set()
    for month in months:
        status = state[month]
        if status["status"] != "verified_complete":
            raise ValueError("partition is not verified complete")
        expected = status["expected_pages"]
        ids = []
        folder = root / month
        hashes = []
        for page in range(1, expected + 1):
            receipt = json.loads((folder / f"p{page:04d}.json").read_text())
            filename = f"p{page:04d}-{receipt['sha256']}.html"
            if receipt["file"] != filename:
                raise ValueError("receipt filename mismatch")
            path = folder / filename
            if path.is_symlink():
                raise ValueError("unexpected symlink")
            raw = path.read_bytes()
            url = source_url(month, page)
            if receipt["url"] != url or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("source receipt mismatch")
            scope = inspect(raw, month, page)
            if scope != receipt["scope"] or scope["reported_total"] != status["source_count"]:
                raise ValueError("partition provenance mismatch")
            hashes.append(receipt["sha256"])
            ids.extend(scope["ids"])
            for row in archive_rows(raw, url):
                entry = {"observation": row, "observed_at": receipt["observed_at"]}
                try:
                    n = normalize(entry)
                    if n["external_id"] in seen:
                        raise ValueError("cross-partition repeated source identity")
                except (ValueError, KeyError) as exc:
                    review.append({"entry": entry, "reason": str(exc)})
                else:
                    seen.add(n["external_id"])
                    accepted.append(entry)
        if len(ids) != len(set(ids)) or len(ids) != status["source_count"]:
            raise ValueError("partition completeness mismatch")
        manifests.append({"month": month, "count": len(ids), "page_sha256": hashes})
    return {"schema": "gpb_deadline_archive_v1", "accepted": accepted,
            "review": review, "completed_partitions": manifests}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--months", nargs="+", required=True)
    a = p.parse_args()
    os.umask(0o077)
    if len(a.months) != len(set(a.months)):
        raise ValueError("duplicate requested months")
    print(json.dumps(prepare(a.root, a.months), ensure_ascii=False))


if __name__ == "__main__":
    main()
