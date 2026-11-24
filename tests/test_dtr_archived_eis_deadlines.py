"""Synthetic archive-only deadline verification: no network, DB or production."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.ops.read_dtr_archived_eis_deadlines import build_archived_evidence
from src.modules.daily_tender_run import eis_archived_deadline as archived

REG = "0845500000526000021"
OTHER = "0845500000526000022"
RUN = "DTR-20261124T050008Z-87f721ac"
URL = f"https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={REG}"
NOW = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)


def html(reg: str = REG, *, clock: str = "09:00", zone: str = "МСК") -> bytes:
    return (
        f"<html><div>Извещение №{reg}</div>"
        '<span class="section__title">Дата и время окончания срока подачи заявок</span>'
        f'<span class="section__info">30.11.2026 {clock} '
        f"<span class='timeZoneName'>({zone})</span></span></html>"
    ).encode()


def snapshot(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "eis"
    file = root / REG / "raw" / archived.RAW_NAME
    file.parent.mkdir(parents=True)
    file.write_bytes(html())
    row = {
        "registry_number": REG,
        "stored_dtr_deadline": None,
        "law_type": "44fz",
        "artifact_type": "public_detail_common_info",
        "source": "external_public_44fz",
        "sha256": sha256(file.read_bytes()).hexdigest(),
        "size_bytes": file.stat().st_size,
        "created_at": NOW - timedelta(hours=2),
        "local_path": str(file),
        "raw_meta": {
            "registry_number": REG,
            "card_url": URL,
            "source_url": URL,
        },
    }
    return root, row


def test_positive_archived_only_and_immutable_filesystem(tmp_path):
    root, row = snapshot(tmp_path)
    path = root / REG / "raw" / archived.RAW_NAME
    original = path.read_bytes()
    report = build_archived_evidence(RUN, [row], root, now=NOW)
    assert report["contract"] == "ta-dtr-archived-eis-deadline-v1"
    assert report["source_network_requests"] == report["database_mutations"] == 0
    assert report["current_revision_verified"] is False
    assert len(report["records"]) == 1
    found = report["records"][0]
    assert found["archived_deadline_utc"] == "2026-11-30T06:00:00+00:00"
    assert found["official_timezone"] == "МСК"
    assert found["artifact_sha256"] == row["sha256"]
    assert found["source_status"] == "ARCHIVED_ONLY"
    assert found["current_revision_verified"] is False
    assert found["stored_dtr_deadline_present"] is False
    assert found["artifact_registered_utc"] == "2026-11-24T11:00:00+00:00"
    assert path.read_bytes() == original


@pytest.mark.parametrize(("field", "value"), [
    ("registry_number", OTHER),
    ("law_type", "223fz"),
    ("source", "unverified_private_mirror"),
    ("artifact_type", "public_detail_documents"),
    ("sha256", "a" * 64),
    ("sha256", "no"),
    ("size_bytes", 12),
    ("size_bytes", True),
    ("size_bytes", archived.MAX_HTML_BYTES + 1),
    ("created_at", NOW + timedelta(minutes=1)),
    ("created_at", NOW.replace(tzinfo=None)),
    ("local_path", "/private/tmp/untrusted/other.html"),
])
def test_corrupt_or_unmatched_artifact_fails_closed(tmp_path, field, value):
    root, row = snapshot(tmp_path)
    row[field] = value
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)


@pytest.mark.parametrize(("key", "value"), [
    ("registry_number", OTHER),
    ("card_url", "https://invalid.example/page"),
    ("source_url", URL.replace("zk20", "223")),
    ("card_url", URL.replace(REG, OTHER)),
])
def test_untrusted_metadata_cannot_be_promoted(tmp_path, key, value):
    root, row = snapshot(tmp_path)
    row["raw_meta"][key] = value
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)


@pytest.mark.parametrize("change", [
    "content_changed",
    "wrong_registry_in_page",
    "date_only",
    "no_timezone",
    "ambiguous_two_fields",
])
def test_original_bytes_need_hash_and_exact_clock(tmp_path, change):
    root, row = snapshot(tmp_path)
    path = root / REG / "raw" / archived.RAW_NAME
    if change == "content_changed":
        path.write_bytes(html(clock="10:00"))
    elif change == "wrong_registry_in_page":
        path.write_bytes(html(reg=OTHER))
    elif change == "date_only":
        path.write_bytes(b"<html>30.11.2026 " + REG.encode() + b"</html>")
    elif change == "no_timezone":
        path.write_bytes(html(zone="UTC"))
    else:
        path.write_bytes(html() + html())
    if change != "content_changed":
        row["sha256"] = sha256(path.read_bytes()).hexdigest()
        row["size_bytes"] = path.stat().st_size
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)


def test_symlink_file_and_writable_source_rejected(tmp_path):
    root, row = snapshot(tmp_path)
    path = root / REG / "raw" / archived.RAW_NAME
    other = tmp_path / "other"
    other.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(other)
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)
    path.unlink()
    path.write_bytes(other.read_bytes())
    path.chmod(0o666)
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)


def test_untrusted_directory_rejected(tmp_path):
    root, row = snapshot(tmp_path)
    sub = root / REG / "raw"
    sub.chmod(0o777)
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        archived.verify_archived_deadline(root, REG, row, now=NOW)


def test_duplicate_rows_and_missing_rows_denied(tmp_path):
    root, row = snapshot(tmp_path)
    for rows in ([], [row, dict(row)], [row] * 13):
        with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
            build_archived_evidence(RUN, rows, root, now=NOW)


def test_untrusted_run_denied(tmp_path):
    root, row = snapshot(tmp_path)
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        build_archived_evidence("DTR-OTHER", [row], root, now=NOW)


def test_no_network_access_in_archive_mode(tmp_path, monkeypatch):
    from urllib import request

    monkeypatch.setattr(
        request, "urlopen",
        lambda *args, **kwargs: pytest.fail("archive reader attempted HTTP"),
    )
    root, row = snapshot(tmp_path)
    assert build_archived_evidence(RUN, [row], root, now=NOW)["source_network_requests"] == 0
