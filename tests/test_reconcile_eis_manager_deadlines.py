"""Offline checks for bounded owner-gated EIS MANAGER_READY reconciliation."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.ops import reconcile_eis_manager_deadlines as module


def _fixture(tmp_path: Path, monkeypatch, *, stale: bool = False):
    root = tmp_path / "manager"
    root.mkdir(mode=0o700)
    originals = tmp_path / "eis-midnight-audit-20261123"
    originals.mkdir(mode=0o700)
    raw = b'{"metadata":{"db_system_id_sha256":"' + b"a" * 64 + b'"}}'
    (originals / "snapshot.json").write_bytes(raw)
    monkeypatch.setattr(module, "SNAPSHOT_SHA", module._hash(raw))
    (root / "official-recheck-html").mkdir(mode=0o700)
    when = datetime.now(UTC) - (timedelta(hours=2) if stale else timedelta(minutes=2))
    rows = []
    proofs = {}
    for n in range(37):
        reg = f"{n:019d}"
        stamp = "2026-11-30T06:00:00+00:00"
        rows.append({
            "id": f"id-{n}", "registry_number": reg,
            "source_url": "https://zakupki.gov.ru/epz/order/notice/ea20/"
                          f"view/common-info.html?regNumber={reg}",
            "new_deadline_utc": stamp, "changed": n < 35,
        })
        html = f"test-page-{reg}".encode()
        (root / "official-recheck-html" / f"{reg}.html").write_bytes(html)
        proofs[reg] = {
            "html_sha256": module._hash(html), "html_bytes": len(html),
            "official_utc": stamp,
        }
    plan = {
        "task_id": "TA-EIS-MANAGER-DEADLINES-20261123",
        "created_at_utc": when.isoformat(),
        "original_audit_snapshot_sha256": module.SNAPSHOT_SHA,
        "original_audit_csv_sha256": module.CSV_SHA,
        "expected_db": list(module.DB_IDENTITY),
        "expected_db_system_sha256": "a" * 64,
        "rows": rows, "fresh_eis_rechecks": proofs,
        "rows_checked": 37, "rows_to_update": 35, "rows_already_exact": 2,
    }
    sha = module._json_write_once(root / "plan.json", plan)
    (root / "plan.sha256").write_text(sha + "\n")

    class FakeAudit:
        @staticmethod
        def extract_exact_eis_deadline(html, registry):
            return {"official_utc": "2026-11-30T06:00:00+00:00"}

        @staticmethod
        def _unique_notice_url(url, registry):
            assert registry in url
            return url

    monkeypatch.setattr(module, "_audit", lambda: FakeAudit())
    return root, sha


def test_verified_plan_accepts_37_exact_sources(tmp_path, monkeypatch):
    root, sha = _fixture(tmp_path, monkeypatch)
    p = module._load_prepared(root, sha)
    assert len(p["rows"]) == 37
    assert sum(x["changed"] for x in p["rows"]) == 35


def test_manifest_sha_mutation_blocks(tmp_path, monkeypatch):
    root, sha = _fixture(tmp_path, monkeypatch)
    with (root / "plan.json").open("a") as f:
        f.write(" ")
    with pytest.raises(module.SourceMismatch, match="SHA mismatch"):
        module._load_prepared(root, sha)


def test_original_source_tamper_blocks(tmp_path, monkeypatch):
    root, sha = _fixture(tmp_path, monkeypatch)
    file = next((root / "official-recheck-html").iterdir())
    file.write_text("changed original")
    with pytest.raises(module.SourceMismatch, match="fresh official original"):
        module._load_prepared(root, sha)


def test_expired_attestation_refuses_write(tmp_path, monkeypatch):
    root, sha = _fixture(tmp_path, monkeypatch, stale=True)
    with pytest.raises(module.SourceMismatch, match="expired"):
        module._load_prepared(root, sha)
    assert len(module._load_prepared(root, sha, require_fresh=False)["rows"]) == 37


def test_unexpected_postgres_system_hash_refused(tmp_path, monkeypatch):
    root, _sha = _fixture(tmp_path, monkeypatch)
    obj = json.loads((root / "plan.json").read_text())
    obj["expected_db_system_sha256"] = "b" * 64
    (root / "plan.json").unlink()
    newsha = module._json_write_once(root / "plan.json", obj)
    (root / "plan.sha256").write_text(newsha + "\n")
    with pytest.raises(module.SourceMismatch, match="system identity"):
        module._load_prepared(root, newsha)


def test_symlink_private_folder_rejected(tmp_path):
    target = tmp_path / "outside"
    target.mkdir(mode=0o700)
    link = tmp_path / "manager"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(module.SourceMismatch, match="symlink"):
        module._private_dir(link)


def test_backup_uses_exclusive_creation_and_sha(tmp_path):
    backup = tmp_path / "backup.json"
    raw = b'{"proof":"original"}'
    sha = module._exclusive_file(backup, raw)
    assert sha == module._hash(raw)
    assert backup.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module._exclusive_file(backup, b"mutated")


def test_prepare_with_existing_root_refuses_overwrite(tmp_path):
    root = tmp_path / "manager"
    root.mkdir(mode=0o700)
    with pytest.raises(module.SourceMismatch, match="already exists"):
        module.prepare(tmp_path, root, datetime.now(UTC))
