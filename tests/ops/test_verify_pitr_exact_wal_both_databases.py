"""Offline-only tests; never starts a container or accesses original backup."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.ops.verify_pitr_exact_wal_both_databases import (
    IDENT,
    WAL_BYTES,
    EvidenceError,
    preflight,
    save_once,
    verify_rows,
)


def make_fixture(tmp_path):
    base = tmp_path/"base-20261121T131504536797Z"/"data"
    base.mkdir(parents=True)
    (base/"backup_manifest").write_bytes(b"original")
    (base/"PG_VERSION").write_text("17\n")
    wal = tmp_path/("wal-"+IDENT)
    wal.mkdir()
    names = ["00000001000000060000007B", "00000001000000060000007C"]
    for name in names:
        with (wal/name).open("wb") as stream:
            stream.truncate(WAL_BYTES)
    source = {"base_path":str(base), "source_system_identifier":IDENT,
              "status":"pass", "live_database_mutated":False,
              "image":"sha256:"+"a"*64}
    target = {"base":str(base), "status":"pass",
              "business_data_mutated":False,
              "base_manifest_sha256":hashlib.sha256(b"original").hexdigest(),
              "restore_point":"arvectum_pitr_check_20261121T131900487923Z",
              "exact_target_observed_in_server_log":True,
              "base_end_lsn":"6/7B288058", "restore_lsn":"6/7E000090",
              "contiguous_wal":names}
    bp = base.parent/"restore-verified.json"
    tp = tmp_path/"named-target.json"
    bp.write_text(json.dumps(source))
    tp.write_text(json.dumps(target))
    return bp, tp, source, target


def test_source_preflight_is_exact_and_offline(tmp_path):
    bp, tp, _, _ = make_fixture(tmp_path)
    result = preflight(bp, tp)
    assert result["wal_count"] == 2
    assert result["point"] == "arvectum_pitr_check_20261121T131900487923Z"


@pytest.mark.parametrize("case", ["manifest_drift","wrong_base","image_not_pinned",
                                 "wal_gap","wal_missing","pg18",
                                 "other_cluster","unknown_target","source_not_verified"])
def test_failure_fails_closed_before_docker(tmp_path, case):
    bp, tp, source, target = make_fixture(tmp_path)
    base = Path(source["base_path"])
    if case == "manifest_drift":
        (base/"backup_manifest").write_bytes(b"changed")
    elif case == "wrong_base":
        target["base"] = "/tmp/other"
    elif case == "image_not_pinned":
        source["image"] = "other"
    elif case == "wal_gap":
        target["contiguous_wal"][1] = "00000001000000060000007E"
    elif case == "wal_missing":
        (base.parent.parent/("wal-"+IDENT)/target["contiguous_wal"][1]).unlink()
    elif case == "pg18":
        (base/"PG_VERSION").write_text("18\n")
    elif case == "other_cluster":
        source["source_system_identifier"] = "123"
    elif case == "unknown_target":
        target["restore_point"] = "invalid-target-value"
    elif case == "source_not_verified":
        source["live_database_mutated"] = True
    bp.write_text(json.dumps(source))
    tp.write_text(json.dumps(target))
    with pytest.raises(EvidenceError):
        preflight(bp, tp)


def test_both_databases_and_exact_log_marker_are_required():
    rows = (
        "EXACT_RESTORE_POINT_OBSERVED_IN_PG_LOG\n"
        +json.dumps({"database":"arvectum", "system_identifier":IDENT, "recovery":False,
                     "revision":"127_private_review_link_corrections",
                     "tenders":64, "new_tables":7})+"\n"
        +json.dumps({"database":"arvectum_data", "system_identifier":IDENT,
                     "recovery":False, "collections":73})+"\n"
    )
    assert verify_rows(rows)["dp_collections"] == 73
    with pytest.raises(EvidenceError, match="no_exact_target_in_server_log"):
        verify_rows(rows.replace("EXACT_RESTORE_POINT_OBSERVED_IN_PG_LOG", ""))
    with pytest.raises(EvidenceError, match="missing_restored_database"):
        verify_rows("\n".join(rows.splitlines()[:2]))


def test_no_receipt_overwrite(tmp_path):
    p = tmp_path/"evidence.json"
    save_once(p, {"status":"PASS", "seven_day":"NOT_PROVEN"})
    with pytest.raises(EvidenceError, match="receipt_already_exists"):
        save_once(p, {"status":"FAKE"})
    assert json.loads(p.read_text())["status"] == "PASS"


def test_isolated_runner_never_mounts_sources_writable_or_enables_network(monkeypatch):
    from types import SimpleNamespace

    from scripts.ops import verify_pitr_exact_wal_both_databases as impl

    calls = []
    stdout = (
        "EXACT_RESTORE_POINT_OBSERVED_IN_PG_LOG\n"
        + json.dumps({"database": "arvectum", "system_identifier": IDENT,
                      "recovery": False, "revision": "127_private_review_link_corrections",
                      "tenders": 64, "new_tables": 7}) + "\n"
        + json.dumps({"database": "arvectum_data", "system_identifier": IDENT,
                      "recovery": False, "collections": 73}) + "\n"
    )

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(impl.subprocess, "run", fake_run)
    result = impl.run_isolated({
        "base": Path("/trusted/base/data"), "wal": Path("/trusted/wal"),
        "image": "sha256:" + "a" * 64, "point": "arvectum_pitr_check_20261121T131900487923Z",
    })
    args, options = calls[0]
    assert result["business_tenders"] == 64
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--pull") + 1] == "never"
    assert "--rm" in args and "--pids-limit" in args
    assert not any(arg == "-p" for arg in args)
    assert "type=bind,src=/trusted/base/data,dst=/backup,readonly" in args
    assert "type=bind,src=/trusted/wal,dst=/wal,readonly" in args
    assert options["check"] is False and options["timeout"] == 420


def test_source_receipt_symlink_rejected(tmp_path):
    bp, tp, _, _ = make_fixture(tmp_path)
    fake = tmp_path/"linked-receipt"
    fake.symlink_to(bp)
    with pytest.raises(EvidenceError, match="receipt_missing_or_unsafe"):
        preflight(fake, tp)
