"""MI-013 production importer must stay read-only by default and fail closed."""
from __future__ import annotations

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


def test_psql_command_tags_are_not_counted_as_preflight_results() -> None:
    with patch.object(importer, "query", return_value="BEGIN\narvectum_data\n3\n0\n0\nCOMMIT\n"):
        assert importer.inspect_target()["required_tables"] == 3
        assert importer.inspect_target()["pq_resources"] == 0


def test_upsert_does_not_reset_existing_review_status() -> None:
    sql = importer.build_apply_sql(importer.stage())
    assert "status=EXCLUDED.status" not in sql
    assert "dp_resources.status IS DISTINCT FROM EXCLUDED.status" not in sql
    assert "'staged_unreviewed'" in sql  # first insert only
    assert "review_status=EXCLUDED.review_status" not in sql


def test_official_backup_bytes_manifest_and_checksum_verified(tmp_path: Path) -> None:
    import hashlib
    import json
    from types import SimpleNamespace

    dump = tmp_path / "data-platform-arvectum_data-TEST.dump"
    contents = b"PGDMP" + b"verified-backup-test"
    dump.write_bytes(contents)
    checksum = hashlib.sha256(contents).hexdigest()
    (tmp_path / (dump.name + ".sha256")).write_text(checksum + "\n")
    manifest = tmp_path / (dump.name + ".manifest.json")
    manifest.write_text(json.dumps({
        "database": importer.DATABASE,
        "container": importer.CONTAINER,
        "backup_file": dump.name,
        "sha256": checksum,
        "bytes": len(contents),
        "format": "postgres-custom",
    }))
    helper = tmp_path / "backup-postgres.sh"
    helper.write_text("#!/bin/sh\nexit 0\n")
    message = (
        f"BACKUP={dump}\nSHA256={checksum}\n"
        f"BYTES={len(contents)}\nMANIFEST={manifest}\n"
    )
    with patch.object(importer, "BACKUP", helper):
        with patch.object(importer.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout=message, stderr="")):
            response = importer.backup(tmp_path)
    assert response["sha256"] == checksum
    assert response["path"] == str(dump)
    assert response["bytes"] == str(len(contents))


def test_mismatching_dump_checksum_blocks_post_backup_import(tmp_path: Path) -> None:
    import hashlib
    import json
    from types import SimpleNamespace

    dump = tmp_path / "backup.dump"
    contents = b"bad content"
    dump.write_bytes(contents)
    fake_sha = hashlib.sha256(b"different contents").hexdigest()
    (tmp_path / "backup.dump.sha256").write_text(fake_sha)
    manifest = tmp_path / "backup.manifest.json"
    manifest.write_text(json.dumps({
        "database": importer.DATABASE,
        "container": importer.CONTAINER,
        "backup_file": dump.name,
        "sha256": fake_sha,
        "bytes": len(contents),
    }))
    helper = tmp_path / "backup-postgres.sh"
    helper.write_text("echo fake")
    message = (
        f"BACKUP={dump}\nSHA256={fake_sha}\n"
        f"BYTES={len(contents)}\nMANIFEST={manifest}\n"
    )
    with patch.object(importer, "BACKUP", helper):
        with patch.object(importer.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout=message, stderr="")):
            import pytest
            with pytest.raises(RuntimeError, match="SHA256 verification failed"):
                importer.backup(tmp_path)
