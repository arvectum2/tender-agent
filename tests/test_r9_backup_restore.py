"""Acceptance contract for R9 backup and restore hardening."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/acceptance/run_r9_backup_restore.py"
RECOVERY_CLI = ROOT / "scripts/ops/r9_recovery.py"
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
import r9_recovery  # noqa: E402

FILES = {
    "backup-restore-result.json",
    "backup-manifest.json",
    "consistent-restore.json",
    "db-only-mismatch.json",
    "filesystem-only-mismatch.json",
    "cross-tenant-mismatch.json",
    "snapshots.json",
    "assertions.json",
    "cleanup.json",
    "commands.log",
    "SHA256SUMS",
}


def _minimal_backup(root: Path) -> Path:
    root.mkdir()
    database = root / "database.dump"
    filesystem = root / "filesystem.tar"
    database.write_bytes(b"database")
    filesystem.write_bytes(b"filesystem")
    tenants = ["customer-a"]
    manifest = {
        "format_version": r9_recovery.FORMAT_VERSION,
        "backup_id": "r9-20260724T000000Z-12345678",
        "created_at": datetime.now(UTC).isoformat(),
        "quiesced": True,
        "exact_file_set": sorted(r9_recovery.BACKUP_FILES),
        "database_sha256": r9_recovery.sha256(database),
        "filesystem_sha256": r9_recovery.sha256(filesystem),
        "database_tenants": tenants,
        "filesystem_tenants": tenants,
        "tenant_scope": tenants,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    return root


def test_backup_restore_matrix_is_consistent_and_fail_closed() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=420,
    )
    evidence = Path(completed.stdout.strip().splitlines()[-1])
    result = json.loads((evidence / "backup-restore-result.json").read_text())
    manifest = json.loads((evidence / "backup-manifest.json").read_text())
    consistent = json.loads((evidence / "consistent-restore.json").read_text())
    db_only = json.loads((evidence / "db-only-mismatch.json").read_text())
    fs_only = json.loads((evidence / "filesystem-only-mismatch.json").read_text())
    cross = json.loads((evidence / "cross-tenant-mismatch.json").read_text())

    assert {path.name for path in evidence.iterdir()} == FILES
    assert result["status"] == "R9_P2_BACKUP_RESTORE_FAIL_CLOSED"
    assert result["backup_created"] is True
    assert result["consistent_restore"] is True
    assert result["db_only_mismatch_fail_closed"] is True
    assert result["filesystem_only_mismatch_fail_closed"] is True
    assert result["cross_tenant_mismatch_rejected"] is True
    assert all(result["assertions"].values())
    assert result["cleanup"]["cleanup_complete"] is True
    assert result["hygiene"] == {"passed": True, "hits": []}
    assert result["checksum_validator"]["valid"] is True

    assert manifest["format_version"] == "r9-recovery-v1"
    assert manifest["quiesced"] is True
    assert "R9-RECOVERY" in manifest["tenant_scope"]
    assert set(manifest["filesystem_tenants"]) == {"R9-RECOVERY"}
    assert set(manifest["filesystem_tenants"]).issubset(
        set(manifest["database_tenants"])
    )
    assert manifest["exact_file_set"] == [
        "database.dump",
        "filesystem.tar",
        "manifest.json",
    ]

    assert consistent["safe"] is True
    assert consistent["receipt"]["database_restored"] is True
    assert consistent["receipt"]["filesystem_restored"] is True
    assert consistent["download"]["status_code"] == 200

    assert db_only["safe"] is True
    assert db_only["download"]["status_code"] == 409
    assert db_only["database"]["artifact"] is not None
    assert db_only["filesystem"]["files"] == []

    assert fs_only["safe"] is True
    assert fs_only["case_request"]["status_code"] == 404
    assert fs_only["database"]["binding"] is None
    assert fs_only["database"]["artifact"] is None
    assert fs_only["filesystem"]["files"]

    assert cross["safe"] is True
    assert cross["rejected"] is True
    assert cross["database"]["table_count"] == 0
    assert cross["filesystem"]["exists"] is False

    rows = (evidence / "SHA256SUMS").read_text().splitlines()
    assert len(rows) == 10
    assert "SHA256SUMS" not in {line.split("  ", 1)[1] for line in rows}


def test_recovery_cli_expected_failure_is_json_and_has_no_traceback(tmp_path) -> None:
    data = tmp_path / "data"
    output = tmp_path / "backups"
    data.mkdir()
    completed = subprocess.run(
        [
            sys.executable,
            str(RECOVERY_CLI),
            "backup",
            "--database-url",
            "postgresql://invalid/unused",
            "--data-dir",
            str(data),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "Traceback" not in completed.stderr
    assert json.loads(completed.stderr) == {
        "ok": False,
        "error": "Backup requires an explicitly quiesced application",
    }


def test_verify_backup_rejects_symlink_and_non_file_entries(tmp_path) -> None:
    backup = _minimal_backup(tmp_path / "backup")
    assert r9_recovery.verify_backup(backup)["tenant_scope"] == ["customer-a"]

    extra = backup / "unexpected-directory"
    extra.mkdir()
    with pytest.raises(r9_recovery.RecoveryError, match="file set"):
        r9_recovery.verify_backup(backup)
    extra.rmdir()

    link = tmp_path / "backup-link"
    link.symlink_to(backup, target_is_directory=True)
    with pytest.raises(r9_recovery.RecoveryError, match="directory is invalid"):
        r9_recovery.verify_backup(link)


def test_restore_database_uses_single_transaction(monkeypatch, tmp_path) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(r9_recovery, "_database_is_empty", lambda _url: True)
    monkeypatch.setattr(
        r9_recovery,
        "_pg_connection",
        lambda _url: ("postgresql://user@db/target", {}),
    )
    monkeypatch.setattr(
        r9_recovery,
        "_run",
        lambda command, _env: commands.append(command),
    )
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"dump")
    r9_recovery.restore_database(
        database_url="postgresql://ignored/target",
        database_dump=dump,
    )
    assert len(commands) == 1
    assert commands[0][0] == "pg_restore"
    assert "--single-transaction" in commands[0]
    assert "--exit-on-error" in commands[0]


def test_restore_cli_failure_diagnostics_redact_connection_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    secret_uri = "postgresql://alice:secret@localhost:5432/test"
    monkeypatch.setattr(
        r9_recovery.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr=(
                f"pg_restore: error at {secret_uri}: "
                "unsupported transaction_timeout"
            ),
        ),
    )
    with pytest.raises(r9_recovery.RecoveryError) as exc:
        r9_recovery._run(["pg_restore", "--dbname", secret_uri], {})
    message = str(exc.value)
    assert message == "pg_restore failed with exit code 1"
    assert "secret" not in message
