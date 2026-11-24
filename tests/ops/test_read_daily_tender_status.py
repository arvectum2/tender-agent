"""Fake/fixture-only regressions for aggregate DTR operator status."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from scripts.ops import read_daily_tender_status as status

NOW = datetime(2026, 11, 24, 6, 10, tzinfo=UTC)
ID = "DTR-20261124T050008Z-87f721ac"


def run(**changes):
    record = {
        "run_id": ID,
        "status": "RUNNING",
        "current_stage": "ANALYZE",
        "started_at": NOW - timedelta(minutes=70),
        "updated_at": NOW - timedelta(minutes=22),
        "has_error": False,
        "error_summary": "PRIVATE RAW DOCUMENT",
        "source_url": "https://example.test/sensitive",
    }
    record.update(changes)
    return record


def group(name, count, minutes):
    return {"status": name, "item_count": count,
            "latest_change": NOW - timedelta(minutes=minutes),
            "customer_name": "SECRET_CUSTOMER"}


def test_safe_running_aggregate_does_not_echo_source_or_errors():
    payload = status.make_snapshot(
        run(), [group("MANAGER_READY", 3, 5), group("PROCESSING", 1, 9),
                group("SCREENED_OUT", 21, 65), group("SHORTLISTED", 4, 62),
                group("DUPLICATE", 4, 67)],
        now=NOW,
    )
    assert payload["scope"] == "arvectum-it"
    assert payload["status"] == "RUNNING"
    assert payload["stage"] == "ANALYZE"
    assert payload["items_total"] == 33
    assert payload["item_counts"]["MANAGER_READY"] == 3
    assert payload["item_counts"]["SHORTLISTED"] == 4
    assert payload["minutes_since_last_record_change"] == 5
    assert payload["error_present"] is False
    assert "PRIVATE" not in str(payload)
    assert "SECRET_CUSTOMER" not in str(payload)
    assert "example.test" not in str(payload)


def test_empty_history_is_explicit_and_bounded():
    assert status.make_snapshot(None, [], now=NOW) == {
        "scope": "arvectum-it", "status": "NO_RUN", "item_counts": {},
    }


def test_untrusted_id_and_labels_are_masked_and_unknown_count_retained():
    payload = status.make_snapshot(
        run(run_id="PRIVATE_ACCOUNT_NUMBER", status="PRIVATE SOURCE DOCUMENT",
            current_stage="Customer A", has_error=True),
        [group("SRC-PRIVATE", 2, 3)], now=NOW,
    )
    assert payload["run_id"] == "REDACTED"
    assert payload["status"] == payload["stage"] == "OTHER"
    assert payload["item_counts"] == {"OTHER": 2}
    assert payload["error_present"] is True
    assert "PRIVATE" not in str(payload)


@pytest.mark.parametrize("bad", [-1, 1.2, "1", None, True])
def test_broken_aggregates_fail_closed(bad):
    with pytest.raises(ValueError, match="Invalid aggregate"):
        status.make_snapshot(run(), [group("PROCESSING", bad, 1)], now=NOW)


class FakeRows:
    def __init__(self, *, first=None, rows=None):
        self.head = first
        self.rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self.head

    def all(self):
        return self.rows


class FakeConnection:
    def __init__(self, head, rows, db_name="arvectum", db_user="arvectum"):
        self.head = head
        self.rows = rows
        self.db_name = db_name
        self.db_user = db_user
        self.commands = []
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement, params=None):
        sql = str(statement).strip()
        self.commands.append((sql, params))
        if sql.startswith("SET TRANSACTION"):
            return None
        if "SELECT current_database()" in sql:
            return FakeRows(first={"database_name": self.db_name, "role_name": self.db_user})
        if "FROM daily_tender_runs" in sql:
            return FakeRows(first=self.head)
        if "FROM daily_tender_run_items" in sql:
            return FakeRows(rows=self.rows)
        raise AssertionError("Unexpected query")

    def rollback(self):
        self.rolled_back = True


class FakeEngine:
    def __init__(self, connection, dialect="postgresql"):
        self.connection = connection
        self.dialect = SimpleNamespace(name=dialect)

    def connect(self):
        return self.connection


def test_read_only_repeatable_read_and_bound_parameters():
    connection = FakeConnection(run(), [group("PROCESSING", 1, 3)])
    report = status.read_snapshot(FakeEngine(connection), now=NOW)
    assert report["item_counts"] == {"PROCESSING": 1}
    assert len(connection.commands) == 4
    assert connection.commands[0][0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    assert "current_database()" in connection.commands[1][0]
    assert connection.commands[2][1] == {"profile": "arvectum-it"}
    assert connection.commands[3][1] == {"run_id": ID}
    assert connection.rolled_back
    assert all("UPDATE " not in sql and "INSERT " not in sql
               for sql, _ in connection.commands)


def test_empty_result_never_queries_items_and_rolls_back():
    connection = FakeConnection(None, [])
    assert status.read_snapshot(FakeEngine(connection), now=NOW)["status"] == "NO_RUN"
    assert len(connection.commands) == 3
    assert connection.rolled_back


def test_non_postgres_target_rejected_without_connection():
    connection = FakeConnection(None, [])
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        status.read_snapshot(FakeEngine(connection, dialect="sqlite"), now=NOW)
    assert connection.commands == []


def test_cli_masks_internal_failure(monkeypatch, capsys):
    from src.shared.db import session as db_session

    class Reject:
        dialect = SimpleNamespace(name="postgresql")

        def connect(self):
            raise RuntimeError("secret=SHOULD_NEVER_PRINT")

    monkeypatch.setattr(db_session, "engine", Reject())
    assert status.main() == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "DTR_READONLY_STATUS_UNAVAILABLE"
    assert "SHOULD_NEVER_PRINT" not in str(output)

@pytest.mark.parametrize(
    ("name", "user"),
    [("staging", "arvectum"), ("arvectum", "root"), ("", ""), ("arvectum_test", "arvectum")],
)
def test_wrong_database_identity_rejected_before_reading_rows(name, user):
    conn = FakeConnection(run(), [], db_name=name, db_user=user)
    with pytest.raises(RuntimeError, match="Unexpected database identity"):
        status.read_snapshot(FakeEngine(conn), now=NOW)
    assert len(conn.commands) == 2
    assert conn.rolled_back
