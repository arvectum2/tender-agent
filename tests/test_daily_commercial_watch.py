"""Offline synthetic tests for the daily source-bound commercial watch runner."""
from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.research import daily_commercial_watch as daily
from scripts.research.commercial_watch import EvidenceRejected

NOW = datetime(2026, 11, 23, 5, 10, tzinfo=UTC)


def _sample():
    return {
        "schema": "arvectum_commercial_watch_v1",
        "generated_for_utc": NOW.isoformat(),
        "sibur": {
            "summary": {"unexpired_relevant": 2},
            "candidates": [
                {
                    "external_id": "123/1", "source": "SIBUR",
                    "title": "Система автоматизации",
                    "deadline_utc": "2026-11-27T09:00:00+00:00",
                    "deadline_msk": "27.11.2026 12:00",
                    "buyer_as_published": None,
                    "organizer_as_published": "ПАО СИБУР",
                    "topic": "АСУ ТП / автоматизация", "price_as_published": None,
                    "priority_score": 100,
                    "novelty": "observed_in_latest_public_capture",
                    "freshness": "current_nonatomic_public_list_not_srm",
                    "evidence_status": "CURRENT_SIBUR_PUBLIC_LIST_CARD_RECHECK",
                    "source_sha256": "a" * 64,
                    "first_party_source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
                    "next_action": "Повторно проверить статус",
                }
            ],
        },
        "geh": {"summary": {"matching_unexpired": 1}, "candidates": []},
    }


def _prepared(tmp_path, monkeypatch):
    geh_root = tmp_path / "geh-root"
    geh_root.mkdir()
    geh = geh_root / "geh-active-refresh-20261123T050000Z"
    geh.mkdir()
    (geh / "guarded-ingest").mkdir()
    (geh / "guarded-ingest" / "state.json").write_text("{}")
    sibur_root = tmp_path / "sibur"
    sibur_root.mkdir()
    watch = tmp_path / "previous-watch.json"
    watch.write_text("{}")
    capture = sibur_root / "current-sibur"
    capture.mkdir()
    out = tmp_path / "reports"

    def fake_compile(**kwargs):
        assert kwargs["geh_root"] == geh_root
        assert kwargs["sibur_capture"] == capture
        return _sample(), geh

    def fake_proof(geh_arg, sibur_arg):
        assert geh_arg == geh
        assert sibur_arg == capture
        return {"original_source": "a" * 64}

    monkeypatch.setattr(daily, "_compile", fake_compile)
    monkeypatch.setattr(daily, "_source_proof", fake_proof)
    return geh_root, sibur_root, watch, capture, out


def _execute(geh, sibur, watch, capture, out, now=NOW):
    return daily.execute(
        geh_root=geh, sibur_root=sibur, sibur_watch=watch,
        existing_sibur_capture=capture, out_root=out, now=now,
        capture_sibur=False,
    )


def test_choose_newest_geh_and_never_fallback_on_incomplete(tmp_path):
    geh_root = tmp_path / "geh"
    geh_root.mkdir()
    older = geh_root / "geh-active-refresh-20261122T102852Z"
    older.mkdir()
    (older / "guarded-ingest").mkdir()
    (older / "guarded-ingest" / "state.json").write_text("{}")
    assert daily.latest_geh(geh_root) == older
    newer = geh_root / "geh-active-refresh-20261123T050142Z"
    newer.mkdir()
    with pytest.raises(EvidenceRejected, match="incomplete"):
        daily.latest_geh(geh_root)
    (newer / "guarded-ingest").mkdir()
    (newer / "guarded-ingest" / "state.json").write_text("{}")
    assert daily.latest_geh(geh_root) == newer


def test_newest_geh_symlink_rejected(tmp_path):
    root = tmp_path / "geh"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (root / "geh-active-refresh-20261123T050142Z").symlink_to(external)
    with pytest.raises(EvidenceRejected, match="symlink"):
        daily.latest_geh(root)


def test_offline_report_has_no_writes_or_capture(tmp_path, monkeypatch):
    geh, _sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(
        daily, "_run_capture",
        lambda *_: pytest.fail("offline replay unexpectedly attempted network"),
    )
    data = daily.build_report_offline(
        geh_root=geh, sibur_capture=capture, sibur_watch=watch, now=NOW,
    )
    assert data["sibur"]["candidates"][0]["external_id"] == "123/1"
    assert not out.exists()


def test_successful_execute_is_atomic_private_and_sha_bound(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    receipt = _execute(geh, sibur, watch, capture, out)
    assert receipt["status"] == "completed"
    assert receipt["production_database_modified"] is False
    assert receipt["external_submissions_sent"] is False
    assert receipt["source_sha256"]["original_source"] == "a" * 64
    content = Path(receipt["report_json"]).read_bytes()
    markdown = Path(receipt["report_markdown"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == receipt["report_json_sha256"]
    assert hashlib.sha256(markdown).hexdigest() == receipt["report_markdown_sha256"]
    assert "Изменения относительно предыдущей коммерческой подборки" in markdown.decode()
    assert "Первый отчёт" in markdown.decode()
    assert json.loads(content)["sibur"]["candidates"][0]["external_id"] == "123/1"
    assert json.loads((out / "last_success.json").read_text()) == receipt
    assert json.loads((out / "last_attempt.json").read_text()) == receipt
    assert out.stat().st_mode & 0o777 == 0o700
    assert Path(receipt["report_json"]).stat().st_mode & 0o777 == 0o600
    assert not any(x.is_symlink() for x in (out / "runs").rglob("*"))


def test_fail_preserves_last_success_and_blocks_last_attempt(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    success = _execute(geh, sibur, watch, capture, out)
    old_json = (out / "last_success.json").read_bytes()

    def failure(**_):
        raise EvidenceRejected("latest GEH admission still in progress")

    monkeypatch.setattr(daily, "_compile", failure)
    with pytest.raises(EvidenceRejected, match="still in progress"):
        _execute(geh, sibur, watch, capture, out, now=NOW.replace(minute=11))
    assert (out / "last_success.json").read_bytes() == old_json
    attempt = json.loads((out / "last_attempt.json").read_text())
    assert attempt["status"] == "blocked"
    assert attempt["error_type"] == "EvidenceRejected"
    assert success["status"] == "completed"


def test_lock_prevents_overlapping_report_even_for_dry_existing_capture(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    out.mkdir(mode=0o700)
    lock = out / ".source-watch.lock"
    with lock.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(EvidenceRejected, match="already running"):
            _execute(geh, sibur, watch, capture, out)
    assert not (out / "last_success.json").exists()


def test_partial_capture_is_blocked_and_never_promoted(tmp_path, monkeypatch):
    geh, sibur, watch, _capture, out = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(
        daily, "_run_capture",
        lambda *_: (_ for _ in ()).throw(EvidenceRejected("incomplete SIBUR public listing")),
    )
    with pytest.raises(EvidenceRejected, match="incomplete"):
        daily.execute(
            geh_root=geh, sibur_root=sibur, sibur_watch=watch,
            existing_sibur_capture=None, capture_sibur=True,
            out_root=out, now=NOW,
        )
    assert json.loads((out / "last_attempt.json").read_text())["status"] == "blocked"
    assert not (out / "last_success.json").exists()


def test_no_source_capture_without_explicit_double_opt_in(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    with pytest.raises(EvidenceRejected, match="exactly one"):
        daily.execute(
            geh_root=geh, sibur_root=sibur, sibur_watch=watch,
            existing_sibur_capture=None, capture_sibur=False, out_root=out, now=NOW,
        )
    with pytest.raises(EvidenceRejected, match="exactly one"):
        daily.execute(
            geh_root=geh, sibur_root=sibur, sibur_watch=watch,
            existing_sibur_capture=capture, capture_sibur=True, out_root=out, now=NOW,
        )


def test_report_delta_is_about_shortlist_not_source_closure():
    current = _sample()
    old = {"shortlist_signature": {
        "sibur:123/1": {
            "title": "Система автоматизации", "price_as_published": None,
            "deadline_utc": "2026-11-24T09:00:00+00:00",
        },
        "geh:old": {
            "title": "ТЭЦ", "price_as_published": None,
            "deadline_utc": "2026-11-24T09:00:00+00:00",
        },
    }}
    delta = daily._report_delta(current, old)
    assert delta["shortlist_added"] == []
    assert delta["shortlist_changed"] == ["sibur:123/1"]
    assert delta["shortlist_not_recommended_now_not_closure"] == ["geh:old"]
    assert delta["baseline"] == "prior_successful_shortlist_not_the_entire_source"


def test_invalid_previous_success_receipt_refuses_new_publication(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    out.mkdir(mode=0o700)
    (out / "last_success.json").write_text('{"status":"in_progress"}')
    with pytest.raises(EvidenceRejected, match="invalid"):
        _execute(geh, sibur, watch, capture, out)
    assert not (out / "runs").exists()
    assert json.loads((out / "last_attempt.json").read_text())["status"] == "blocked"


def test_private_dir_symlink_rejected(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    external = tmp_path / "outside"
    external.mkdir()
    out.symlink_to(external)
    with pytest.raises(EvidenceRejected, match="symlink"):
        _execute(geh, sibur, watch, capture, out)
    assert list(external.iterdir()) == []


def test_disk_safety_fails_closed_before_source_get(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(daily.shutil, "disk_usage", lambda *_: type(
        "Usage", (), {"free": 128})())
    with pytest.raises(EvidenceRejected, match="insufficient"):
        _execute(geh, sibur, watch, capture, out)
    assert json.loads((out / "last_attempt.json").read_text())["status"] == "blocked"


def test_source_proof_requires_real_readable_files(tmp_path):
    geh, sibur = tmp_path / "geh", tmp_path / "sibur"
    geh.mkdir()
    sibur.mkdir()
    with pytest.raises(EvidenceRejected, match="source proof unavailable"):
        daily._source_proof(geh, sibur)



def test_source_capture_lock_rejects_second_caller_even_with_another_report_root(
    tmp_path,
):
    root = tmp_path / "sibur-source"
    root.mkdir()
    lock = root / ".daily-public-capture.lock"
    with lock.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(EvidenceRejected, match="another SIBUR"):
            daily._run_capture(root, "20261123T060001000000Z")
    assert not list(root.glob("daily-commercial-*"))


def test_report_private_root_does_not_change_existing_shared_permissions(
    tmp_path, monkeypatch,
):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    out.mkdir(mode=0o755)
    out.chmod(0o755)
    with pytest.raises(EvidenceRejected, match="unsafe group/other"):
        _execute(geh, sibur, watch, capture, out)
    assert out.stat().st_mode & 0o777 == 0o755
    assert list(out.iterdir()) == []


def test_second_success_reports_only_actual_shortlist_change(tmp_path, monkeypatch):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    first = _execute(geh, sibur, watch, capture, out)
    assert first["shortlist_delta"]["baseline"] == "first_run_no_prior_commercial_shortlist"
    next_data = _sample()
    next_data["sibur"]["candidates"][0]["deadline_utc"] = "2026-11-28T09:00:00+00:00"
    monkeypatch.setattr(daily, "_compile", lambda **_: (next_data, geh / "geh-active-refresh-20261123T050000Z"))
    second = _execute(geh, sibur, watch, capture, out, now=NOW.replace(minute=12))
    assert second["shortlist_delta"]["shortlist_added"] == []
    assert second["shortlist_delta"]["shortlist_changed"] == ["sibur:123/1"]
    markdown = Path(second["report_markdown"]).read_text()
    assert "Изменились срок" in markdown
    assert "sibur:123/1" in markdown
    assert Path(first["report_json"]).is_file()
    assert second["status"] == "completed"



def test_previous_report_tampering_is_blocked_before_delta_publication(
    tmp_path, monkeypatch,
):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    good = _execute(geh, sibur, watch, capture, out)
    prior = Path(good["report_json"])
    prior.write_text(prior.read_text() + "unverified corruption")
    with pytest.raises(EvidenceRejected, match="receipt SHA"):
        _execute(geh, sibur, watch, capture, out, now=NOW.replace(minute=11))
    assert json.loads((out / "last_attempt.json").read_text())["status"] == "blocked"
    assert json.loads((out / "last_success.json").read_text())["run_id"] == good["run_id"]


def test_previous_report_pointer_outside_private_runs_is_rejected(
    tmp_path, monkeypatch,
):
    geh, sibur, watch, capture, out = _prepared(tmp_path, monkeypatch)
    _execute(geh, sibur, watch, capture, out)
    receipt_path = out / "last_success.json"
    receipt = json.loads(receipt_path.read_text())
    other = tmp_path / "other.txt"
    other.write_text("other")
    receipt["report_json"] = str(other)
    receipt["report_json_sha256"] = hashlib.sha256(other.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(EvidenceRejected, match="SHA is inconsistent"):
        _execute(geh, sibur, watch, capture, out, now=NOW.replace(minute=11))
