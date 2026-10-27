"""MI-013 production importer must stay read-only by default and fail closed."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/market_intelligence"
sys.path.insert(0, str(SCRIPTS))
try:
    import import_pq_postgres_v12 as importer
finally:
    sys.path.remove(str(SCRIPTS))


def test_stage_exactly_71_deterministic_rated_source_lots() -> None:
    rows = importer.stage()
    assert len(rows) == 71
    assert len({r["canonical_uri"] for r in rows}) == 71
    assert len({r["external_id"] for r in rows}) == 71
    assert all(r["collection_id"] == importer.COLLECTION for r in rows)
    assert sum(r["source_record"]["procedure_id"] == "32616474682" for r in rows) == 2
    assert sum(r["source_record"]["procedure_id"] == "32616435269" for r in rows) == 1


def test_generated_transaction_targets_only_dedicated_collection_and_records() -> None:
    sql = importer.build_apply_sql(importer.stage())
    assert sql.startswith("\nBEGIN;")
    assert sql.count("COMMIT;") == 1
    assert "arvectum_data" in sql
    assert "arvectum-market-pq-6-35kv" in sql
    assert "dp_collections" in sql
    assert "dp_resources" in sql
    assert "dp_records" in sql
    assert "cross-tenant resource collision" in sql
    assert "ON CONFLICT (resource_id) DO UPDATE" in sql
    assert "ON CONFLICT (record_id) DO UPDATE" in sql
    assert "dp_records.revision+1" in sql
    assert "post-import resource count mismatch" in sql
    assert "452016000.01" not in sql  # encoded untrusted source JSON, no interpolated quotes
    assert "DROP TABLE dp_" not in sql
    assert "DELETE FROM dp_" not in sql
    assert "CREATE TABLE dp_" not in sql


def test_default_cli_never_invokes_psql_or_creates_backup() -> None:
    with patch.object(importer, "inspect_target", side_effect=AssertionError("would read DB")):
        with patch.object(importer, "query", side_effect=AssertionError("would mutate DB")):
            with patch.object(importer, "backup", side_effect=AssertionError("would backup")):
                with patch.object(sys, "argv", ["import_pq_postgres_v12.py"]):
                    assert importer.main() == 0


def test_apply_refuses_without_specific_approval_or_backup() -> None:
    with patch.object(importer, "inspect_target", return_value={
        "database": "arvectum_data", "required_tables": 3,
        "pq_resources": 0, "pq_records": 0,
    }):
        with patch.object(importer, "query", side_effect=AssertionError("should not execute")):
            with patch.object(importer, "backup", side_effect=AssertionError("should not create")):
                with patch.object(sys, "argv", ["import_pq_postgres_v12.py", "--apply"]):
                    try:
                        importer.main()
                    except SystemExit as exc:
                        assert "Owner must approve" in str(exc)
                    else:
                        raise AssertionError("write path bypassed approval gate")


def test_preflight_requires_correct_database_and_three_tables() -> None:
    with patch.object(importer, "query", return_value="arvectum_data\n3\n0\n0\n"):
        target = importer.inspect_target()
        assert target == {
            "database": "arvectum_data",
            "required_tables": 3,
            "pq_resources": 0,
            "pq_records": 0,
        }
    with patch.object(importer, "query", return_value="arvectum\n3\n0\n0\n"):
        try:
            importer.inspect_target()
        except RuntimeError as exc:
            assert "schema not verified" in str(exc)
        else:
            raise AssertionError("wrong database accepted")
