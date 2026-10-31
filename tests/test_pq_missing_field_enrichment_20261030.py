import json
from pathlib import Path

import pytest

from scripts.market_intelligence.enrich_pq_missing_field import (
    digest,
    prepare,
    validate,
)

MANIFEST = Path("data/market_intelligence/power_quality/field_enrichment_20261030_4657777.v1.json")


def test_source_sha_and_exact_quote():
    assert prepare(MANIFEST)["value"] == 6


def test_rejects_overwriting_existing_value():
    m = prepare(MANIFEST)
    data = {"quantity": 6, "evidence": [{"url": m["source_url"], "sha256": m["source_sha256"]}]}
    row = {"id": m["canonical_id"], "owner": "tender-agent", "data": data,
           "hash": digest(data), "rev": 1}
    m["expected_content_hash"] = row["hash"]
    with pytest.raises(RuntimeError, match="already set"):
        validate(m, row)


def test_rejects_source_sha_drift(tmp_path):
    m = json.loads(MANIFEST.read_text())
    m["source_sha256"] = "0" * 64
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="SHA drift"):
        prepare(p)
