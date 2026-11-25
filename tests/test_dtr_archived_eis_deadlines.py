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
        "item_law": "44fz",
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


def test_operator_transaction_explicit_read_only_and_scoped_select(tmp_path, monkeypatch, capsys):
    import json

    from scripts.ops import read_dtr_archived_eis_deadlines as operator

    root, row = snapshot(tmp_path)

    class Result:
        def mappings(self):
            return [row]

    class Identity:
        def mappings(self):
            return self

        def first(self):
            return {"database_name": "arvectum", "role_name": "arvectum"}

    class ReadOnlyConnection:
        def __init__(self):
            self.commands = []
            self.rolled_back = False

        def execute(self, query, params=None):
            cmd = str(query).strip()
            self.commands.append(cmd)
            if len(self.commands) == 1:
                assert cmd == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                assert params is None
                return None
            if len(self.commands) == 2:
                assert "current_database()" in cmd
                return Identity()
            assert len(self.commands) == 3
            assert cmd.lstrip().startswith("SELECT ")
            assert "LEFT JOIN procurement_raw_artifacts" in cmd
            assert "r.profile_id = :profile" in cmd
            assert params == {
                "run_id": RUN,
                "item_status": "MANAGER_READY",
                "artifact_type": "public_detail_common_info",
                "profile": "arvectum-it",
            }
            return Result()

        def rollback(self):
            self.rolled_back = True

    class Engine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

        def __init__(self):
            self.conn = ReadOnlyConnection()

        def connect(self):
            class Context:
                def __enter__(inner):
                    return self.conn

                def __exit__(inner, *_args):
                    return None
            return Context()

    engine = Engine()
    monkeypatch.setattr(operator, "engine", engine)
    rc = operator.main(["--run-id", RUN, "--archive-root", str(root)])
    output = capsys.readouterr()
    assert rc == 0 and not output.err
    report = json.loads(output.out)
    assert report["read_only"] is True
    assert report["database_mutations"] == report["source_network_requests"] == 0
    assert engine.conn.rolled_back
    assert len(engine.conn.commands) == 3


def test_operator_database_failure_no_secret_leak(tmp_path, monkeypatch, capsys):
    from sqlalchemy.exc import OperationalError

    from scripts.ops import read_dtr_archived_eis_deadlines as operator

    root, _ = snapshot(tmp_path)

    class Engine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

        def connect(self):
            raise OperationalError("SELECT secret_source", params=None, orig=Exception("SECRET_TOKEN"))

    monkeypatch.setattr(operator, "engine", Engine())
    rc = operator.main(["--run-id", RUN, "--archive-root", str(root)])
    out = capsys.readouterr()
    assert rc == 2
    assert out.out == ""
    assert out.err.strip() == "ARCHIVED_EIS_UNVERIFIED"


def test_sql_preserves_missing_artifacts_and_rejects_other_profile():
    """Execute the actual SELECT, not a mocked successful source join."""
    import sqlite3

    from scripts.ops.read_dtr_archived_eis_deadlines import SELECT_EVIDENCE

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE daily_tender_runs (run_id TEXT, profile_id TEXT);
            CREATE TABLE daily_tender_run_items
                (run_id TEXT, registry_number TEXT, status TEXT, law TEXT, deadline_at TEXT);
            CREATE TABLE procurement_tenders (id INTEGER, registry_number TEXT, law_type TEXT);
            CREATE TABLE procurement_raw_artifacts
                (tender_id INTEGER, artifact_type TEXT, source TEXT, local_path TEXT,
                 sha256 TEXT, size_bytes INTEGER, raw_meta TEXT, created_at TEXT);
        """)
        conn.executemany("INSERT INTO daily_tender_runs VALUES (?, ?)", [
            (RUN, "arvectum-it"), ("other-run", "unrelated-profile"),
        ])
        no_tender = "0845500000526000023"
        excluded = "0845500000526000024"
        conn.executemany("INSERT INTO daily_tender_run_items VALUES (?, ?, ?, ?, NULL)", [
            (RUN, REG, "MANAGER_READY", "44fz"),
            (RUN, OTHER, "MANAGER_READY", "44fz"),
            (RUN, no_tender, "MANAGER_READY", "44fz"),
            (RUN, excluded, "SCREENED_OUT", "44fz"),
            ("other-run", REG, "MANAGER_READY", "44fz"),
        ])
        conn.executemany("INSERT INTO procurement_tenders VALUES (?, ?, ?)", [
            (1, REG, "44fz"), (2, OTHER, "44fz"),
        ])
        conn.executemany("INSERT INTO procurement_raw_artifacts VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL)", [
            (1, "public_detail_common_info", "external_public_44fz"),
            (2, "unrelated_artifact", "external_public_44fz"),
        ])
        params = {
            "run_id": RUN, "item_status": "MANAGER_READY",
            "artifact_type": "public_detail_common_info", "profile": "arvectum-it",
        }
        rows = [dict(r) for r in conn.execute(str(SELECT_EVIDENCE), params)]
        assert [row["registry_number"] for row in rows] == [REG, OTHER, no_tender]
        assert rows[0]["artifact_type"] == "public_detail_common_info"
        assert rows[1]["artifact_type"] is None
        assert rows[2]["law_type"] is None
        assert list(conn.execute(str(SELECT_EVIDENCE), {**params, "run_id": "other-run"})) == []
        conn.execute("INSERT INTO procurement_raw_artifacts VALUES (1, 'public_detail_common_info', 'external_public_44fz', NULL, NULL, NULL, NULL, NULL)")
        rows = list(conn.execute(str(SELECT_EVIDENCE), params))
        assert [row["registry_number"] for row in rows].count(REG) == 2


@pytest.mark.parametrize("missing_tender", [False, True])
def test_partial_archive_rejected_even_with_one_valid_row(tmp_path, missing_tender):
    root, row = snapshot(tmp_path)
    missing = dict.fromkeys(row)
    missing.update(registry_number=OTHER, item_law="44fz",
                   law_type=None if missing_tender else "44fz")
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        build_archived_evidence(RUN, [row, missing], root, now=NOW)


@pytest.mark.parametrize("law", [None, "223fz", "unknown"])
def test_wrong_item_law_rejected(tmp_path, law):
    root, row = snapshot(tmp_path)
    row["item_law"] = law
    with pytest.raises(archived.ArchivedDeadlineError, match="archive_unverified"):
        build_archived_evidence(RUN, [row], root, now=NOW)


@pytest.mark.parametrize("database,role,missing_evidence,expect_select", [
    ("arvectum_local", "arvectum", False, False),
    ("arvectum", "unexpected_role", False, False),
    ("arvectum", "arvectum", True, True),
])
def test_scope_failure_rolls_back_and_never_emits_partial_json(
    tmp_path, monkeypatch, capsys, database, role, missing_evidence, expect_select,
):
    from types import SimpleNamespace

    from scripts.ops import read_dtr_archived_eis_deadlines as operator

    root, row = snapshot(tmp_path)
    commands = []
    rollbacks = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params=None):
            commands.append(str(query))
            if len(commands) == 1:
                assert "REPEATABLE READ READ ONLY" in commands[-1]
                return None
            if len(commands) == 2:
                return SimpleNamespace(mappings=lambda: SimpleNamespace(
                    first=lambda: {"database_name": database, "role_name": role}
                ))
            assert expect_select
            assert params["profile"] == "arvectum-it"
            rows = [row, {"registry_number": OTHER, "item_law": "44fz"}]
            return SimpleNamespace(mappings=lambda: rows if missing_evidence else [row])

        def rollback(self):
            rollbacks.append(True)

    fake = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=Connection)
    monkeypatch.setattr(operator, "engine", fake)
    assert operator.main(["--run-id", RUN, "--archive-root", str(root)]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "ARCHIVED_EIS_UNVERIFIED"
    assert len(commands) == (3 if expect_select else 2)
    assert rollbacks == [True]


def test_non_postgres_rejected_before_connection(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from scripts.ops import read_dtr_archived_eis_deadlines as operator

    fake = SimpleNamespace(
        dialect=SimpleNamespace(name="sqlite"),
        connect=lambda: pytest.fail("must reject non-PostgreSQL before connection"),
    )
    monkeypatch.setattr(operator, "engine", fake)
    assert operator.main(["--run-id", RUN, "--archive-root", str(tmp_path)]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "ARCHIVED_EIS_UNVERIFIED"


@pytest.mark.parametrize("failure_at", [1, 2, 3])
def test_operator_sql_error_rolls_back_without_partial_output(
    tmp_path, monkeypatch, capsys, failure_at,
):
    from types import SimpleNamespace

    from sqlalchemy.exc import OperationalError

    from scripts.ops import read_dtr_archived_eis_deadlines as operator

    commands = []
    rollbacks = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params=None):
            commands.append(str(query))
            if len(commands) == failure_at:
                raise OperationalError("SELECT secret_source", None, Exception("SECRET_TOKEN"))
            if len(commands) == 2:
                return SimpleNamespace(mappings=lambda: SimpleNamespace(
                    first=lambda: {"database_name": "arvectum", "role_name": "arvectum"}
                ))
            return None

        def rollback(self):
            rollbacks.append(True)

    monkeypatch.setattr(operator, "engine", SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=Connection,
    ))
    assert operator.main(["--run-id", RUN, "--archive-root", str(tmp_path)]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "ARCHIVED_EIS_UNVERIFIED"
    assert len(commands) == failure_at
    assert rollbacks == [True]
