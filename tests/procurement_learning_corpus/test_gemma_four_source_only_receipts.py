"""Owner-private immutable local Gemma source-only run receipts."""
from __future__ import annotations

import json
import stat

import pytest

from scripts.procurement_llm import probe_gemma_source_repair as p


def _fixture_payload(mode: str, variant: str) -> dict:
    return {
        "mode": mode,
        "experiment_variant": variant,
        "selected_section_ids": list(p.IDS),
        "canonical_database_modified": False,
        "gold_promoted": False,
        "saved_run": False,
        "sections": [],
    }


def test_final4_receipt_unique_0600_and_cannot_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "OUT", tmp_path / "protected")
    result = p._save_once(_fixture_payload("source_only_local_gemma", "final4"))
    assert result.name == "final4-result.json"
    assert stat.S_IMODE(result.stat().st_mode) == 0o600
    assert stat.S_IMODE(result.parent.stat().st_mode) == 0o700
    assert json.loads(result.read_text())["canonical_database_modified"] is False
    with pytest.raises(FileExistsError):
        p._save_once(_fixture_payload("source_only_local_gemma", "final4"))


def test_prior_archived_receipts_left_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "OUT", tmp_path / "protected")
    old = p._save_once(_fixture_payload("source_only_local_gemma", "baseline"))
    old_hash = old.read_bytes()
    newest = p._save_once(_fixture_payload("source_only_local_gemma", "final4"))
    assert newest != old
    assert old.read_bytes() == old_hash


def test_private_directory_symlink_is_rejected(tmp_path, monkeypatch):
    original = tmp_path / "safe"
    original.mkdir()
    original.chmod(0o700)
    linked = tmp_path / "evil-symlink"
    linked.symlink_to(original)
    monkeypatch.setattr(p, "OUT", linked)
    with pytest.raises(ValueError, match="private"):
        p._save_once(_fixture_payload("source_only_local_gemma", "final4"))


def test_empty_or_unknown_section_rejected_before_db_engine(monkeypatch):
    monkeypatch.setattr(p, "create_engine", lambda *args: pytest.fail("must not create a DB engine"))
    for ids in [(), ("contract_terms", "unsupported")]:
        with pytest.raises(ValueError, match="only supported"):
            p.actual_probe(invoke_llm=False, selected_section_ids=ids)


def test_local_approved_probe_entrypoint_is_not_a_postgresql_history_write():
    from scripts.runtime.verified_procurement_runtime import OPERATIONS

    operation = OPERATIONS["probe_final4"]
    assert operation[-2:] == ("--variant", "final4")
    assert "--apply" not in operation
    assert "source_quality_rerun" not in operation
