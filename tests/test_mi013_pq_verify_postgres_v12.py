"""Read-only MI-013 post-import acceptance against Data Platform PostgreSQL."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "market_intelligence"
sys.path.insert(0, str(SCRIPTS))
try:
    import verify_pq_postgres_v12 as verifier
finally:
    sys.path.remove(str(SCRIPTS))


def _example() -> dict:
    return {
        "database": verifier.DATABASE,
        "collection_id": verifier.COLLECTION,
        "collection_count": 1,
        "pq_resources": 71,
        "pq_records": 71,
        "unique_canonical_ids": 71,
        "unreviewed_records": 71,
        "missing_source_urls": 0,
        "joint_besk_lot_count": 2,
        "joint_besk_distinct_lots": 2,
        "original_10kv_mpu_evidence": 1,
        "other_collections": 26,
        "other_resources": 2192,
        "all_documents": 2192,
    }


def test_sql_is_read_only_and_targets_only_mi013_acceptance() -> None:
    sql = verifier.build_snapshot_query()
    assert sql.startswith("\nBEGIN READ ONLY;")
    assert sql.count("COMMIT;") == 1
    assert "FROM dp_records" in sql
    assert "FROM dp_resources" in sql
    assert "FROM dp_collections" in sql
    assert "FROM dp_documents" in sql
    assert "335351974.38" in sql
    assert "32616474682" in sql
    for forbidden in ("INSERT INTO", "DELETE FROM", "UPDATE dp_", "TRUNCATE", "ALTER TABLE"):
        assert forbidden not in sql


def test_snapshot_parses_real_psql_tags_and_json() -> None:
    expected = _example()
    response = "BEGIN\n" + json.dumps(expected) + "\nCOMMIT\n"
    with patch.object(verifier, "query", return_value=response):
        assert verifier.snapshot() == expected
    verifier.verify_imported(expected)


def test_snapshot_rejects_other_database() -> None:
    payload = _example()
    payload["database"] = "arvectum"
    with patch.object(verifier, "query", return_value=json.dumps(payload)):
        with pytest.raises(RuntimeError, match="unexpected"):
            verifier.snapshot()


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("collection_count", 0),
        ("pq_resources", 70),
        ("pq_records", 72),
        ("unique_canonical_ids", 70),
        ("unreviewed_records", 70),
        ("missing_source_urls", 1),
        ("joint_besk_lot_count", 1),
        ("joint_besk_distinct_lots", 1),
        ("original_10kv_mpu_evidence", 0),
    ],
)
def test_acceptance_rejects_missing_or_incorrect_data(field: str, wrong: int) -> None:
    payload = _example()
    payload[field] = wrong
    with pytest.raises(ValueError, match=field):
        verifier.verify_imported(payload)
