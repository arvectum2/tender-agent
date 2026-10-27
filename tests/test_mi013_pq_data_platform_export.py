"""MI-013 Data Platform handoff: stable IDs, hashes and no fabricated award data."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/market_intelligence/export_pq_data_platform.py"


def exported() -> list[dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True,
        timeout=25,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def test_export_has_60_unique_stable_resources_and_verifiable_hashes() -> None:
    rows = exported()
    assert len(rows) == 60
    assert len({r["resource_id"] for r in rows}) == 60
    assert len({r["canonical_uri"] for r in rows}) == 60
    assert all(r["collection_id"] == "arvectum-market-pq-6-35kv" for r in rows)
    assert all(r["status"] == "staged_unreviewed" for r in rows)
    for item in rows:
        rid = hashlib.sha256(item["external_id"].encode("utf-8")).hexdigest()
        assert item["resource_id"] == rid[:48]
        assert item["canonical_uri"] == "urn:arvectum:pq:procurement:" + rid
        source_text = json.dumps(
            item["source_record"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        )
        assert item["content_hash"] == hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        assert item["metadata"]["research_not_market_population"] is True
        assert item["metadata"]["source_urls"]
        assert all(u.startswith("https://") for u in item["metadata"]["source_urls"])


def test_export_never_promotes_unverified_suppliers_or_awards() -> None:
    rows = exported()
    confirmed = [r for r in rows if r["metadata"]["original_primary_registry_verified"]]
    assert len(confirmed) == 4
    for row in rows:
        if row["source_record"].get("supplier_verified") is not True:
            assert row["metadata"]["winning_supplier_only_if_verified"] is None
    archived = [
        row for row in rows
        if row["external_id"].startswith(("commercial:5534/", "commercial:5631/"))
    ]
    assert len(archived) == 2
    assert all(r["metadata"]["publication_date"] is None for r in archived)
    assert all(r["metadata"]["deadline_date"] for r in archived)
