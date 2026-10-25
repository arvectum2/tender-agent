"""Read-only planning and strictly bounded source acquisition tests."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_history_plan import (
    execute_plan,
    plan_history,
)


def _verified_day(root: Path, region: str, day: date, subsystem: str) -> Path:
    dt = "purchaseNotice" if subsystem == "RI223" else "epNotificationEF2020"
    month = root / subsystem / dt / day.isoformat()
    saved = month / f"region-{region}" / "archive-001" / "documentation-archive.zip"
    saved.parent.mkdir(parents=True)
    saved.write_bytes(b"original source ZIP bytes for test")
    receipt = {
        "subsystem": subsystem, "document_type": dt,
        "region": region, "exact_date": day.isoformat(),
        "status": "complete_with_archive_scan",
        "archive_scan_complete": True,
        "archive_count": 1,
        "archives": [{
            "index": 1,
            "archive_sha256": hashlib.sha256(saved.read_bytes()).hexdigest(),
            "xml_documents_inspected": 1,
        }],
    }
    (month / f"region-{region}.json").write_text(json.dumps(receipt))
    return saved


def _plan(root: Path, *, max_calls: int = 4):
    return plan_history(
        root=root, first=date(2024, 1, 1), last=date(2024, 7, 31),
        regions=["77", "78"], subsystems=["RI223", "PRIZ"],
        max_calls=max_calls,
    )


def test_dry_run_selects_broad_months_without_network(tmp_path: Path):
    result = _plan(tmp_path)
    assert result["selected_calls"] == 4
    assert len({row["date"][:7] for row in result["selected"]}) == 4
    assert len({(row["region"], row["subsystem"]) for row in result["selected"]}) >= 2
    assert result["source_day_status"]["missing"] == 213 * 2 * 2
    assert result["dry_run"] is True
    assert result["national_completeness_achieved"] is False


def test_only_missing_or_new_regions_selected(tmp_path: Path):
    first = _plan(tmp_path)
    target = first["selected"][0]
    day = date.fromisoformat(target["date"])
    _verified_day(tmp_path, target["region"], day, target["subsystem"])
    next_plan = _plan(tmp_path)
    assert target not in next_plan["selected"]
    assert next_plan["source_day_status"]["verified_day"] == 1


def test_original_tamper_aborts_whole_batch(tmp_path: Path):
    saved = _verified_day(tmp_path, "77", date(2024, 2, 15), "RI223")
    saved.write_bytes(b"modified")
    with pytest.raises(ValueError, match="Invalid original EIS evidence"):
        _plan(tmp_path)


def test_incomplete_day_excluded_from_automatic_overwrite(tmp_path: Path):
    target = tmp_path / "RI223/purchaseNotice/2024-02-15/region-77.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "region": "77", "subsystem": "RI223", "document_type": "purchaseNotice",
        "exact_date": "2024-02-15", "status": "retryable_network_failure",
        "archive_scan_complete": False,
    }))
    result = _plan(tmp_path)
    assert not any(row["date"] == "2024-02-15" and row["region"] == "77"
                   and row["subsystem"] == "RI223" for row in result["selected"])


@pytest.mark.parametrize("max_calls", [0, 13, -1, 100])
def test_budget_guard(tmp_path: Path, max_calls: int):
    with pytest.raises(ValueError, match="max_calls"):
        _plan(tmp_path, max_calls=max_calls)


def test_execute_plan_calls_approved_collector_once_per_source(tmp_path: Path, monkeypatch):
    calls = []

    def fake_collect(**kwargs):
        calls.append(kwargs)
        day = kwargs["first"]
        region = kwargs["regions"][0]
        subsystem = kwargs["subsystem"]
        _verified_day(tmp_path, region, day, subsystem)
        return [{"status": "complete_with_archive_scan"}]

    monkeypatch.setattr(
        "src.modules.market_intelligence.eis_history_plan.collect", fake_collect,
    )
    plan = _plan(tmp_path, max_calls=2)
    rows = execute_plan(
        plan=plan, root=tmp_path, ontology={}, client=object(),
        minimum_pause_seconds=0,
    )
    assert len(rows) == 2
    assert all(row["status"] == "verified_day" for row in rows)
    assert len(calls) == 2
    assert all(call["download_archives"] is True for call in calls)
    assert all(call["max_requests"] == 1 for call in calls)


def test_resume_is_idempotent_under_rerun(tmp_path: Path, monkeypatch):
    count = 0

    def fake_collect(**kwargs):
        nonlocal count
        count += 1
        _verified_day(tmp_path, kwargs["regions"][0], kwargs["first"], kwargs["subsystem"])
        return [{"status": "complete_with_archive_scan"}]

    monkeypatch.setattr("src.modules.market_intelligence.eis_history_plan.collect", fake_collect)
    plan = _plan(tmp_path, max_calls=1)
    first = execute_plan(plan=plan, root=tmp_path, ontology={}, client=object(),
                         minimum_pause_seconds=0)
    second = execute_plan(plan=plan, root=tmp_path, ontology={}, client=object(),
                          minimum_pause_seconds=0)
    assert first[0]["status"] == "verified_day"
    assert second[0]["status"] == "already_verified"
    assert count == 1


def test_transient_failure_stops_batch(tmp_path: Path, monkeypatch):
    def fake_collect(**kwargs):
        return [{"status": "retryable_network_failure"}]

    monkeypatch.setattr("src.modules.market_intelligence.eis_history_plan.collect", fake_collect)
    plan = _plan(tmp_path, max_calls=4)
    rows = execute_plan(
        plan=plan, root=tmp_path, ontology={}, client=object(),
        minimum_pause_seconds=0,
    )
    assert len(rows) == 1
    assert rows[0]["soap_receipt_status"] == "retryable_network_failure"
    assert rows[0]["status"] == "missing"


def test_symlink_and_legacy_source_root_rejected(tmp_path: Path):
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "UNTRUSTED_REGION_COLLISION.json").write_text("{}")
    with pytest.raises(ValueError, match="Legacy"):
        _plan(root)
    symlink = tmp_path / "link"
    symlink.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="Legacy"):
        _plan(symlink)

def test_broad_temporal_spread_early_small_budget(tmp_path: Path):
    result = plan_history(
        root=tmp_path, first=date(2023, 10, 25), last=date(2026, 10, 25),
        regions=["77", "78"], subsystems=["RI223", "PRIZ"], max_calls=8,
    )
    assert len({x["date"][:4] for x in result["selected"]}) >= 3


def test_orphaned_region_archive_cannot_be_overwritten(tmp_path: Path):
    orphan = tmp_path / "RI223/purchaseNotice/2024-02-15/region-77/archive-001"
    orphan.mkdir(parents=True)
    (orphan / "documentation-archive.zip").write_bytes(b"untrusted original")
    with pytest.raises(ValueError, match="Orphaned"):
        _plan(tmp_path)
