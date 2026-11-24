"""Read-only, redacted CLI diagnostics; no DB, source fetch or retry."""
import json
from types import SimpleNamespace

from scripts.run_daily_tender_run import _exit_code_with_diagnostic


def _run(number: int, status: str = "WAITING_HUMAN", error=None):
    return SimpleNamespace(
        run_id=f"DTR-202611{number:02d}T050015Z-509e6c24",
        status=status,
        error_summary=error,
        source_url="https://private.example/secret?token=NEVER_PRINT",
        customer_name="PRIVATE_CUSTOMER",
    )


def test_clean_today_and_clean_history_return_zero_without_noise(capsys):
    assert _exit_code_with_diagnostic(
        [_run(21), _run(22, "COMPLETED")], _run(23)
    ) == 0
    assert capsys.readouterr().err == ""


def test_clean_today_historical_failures_keep_exit20_and_explain_origin(capsys):
    old = _run(19, error="raw private error api-key SECRET_NEVERSHOW")
    now = _run(23)
    assert _exit_code_with_diagnostic([old], now) == 20
    diag = json.loads(capsys.readouterr().err)
    assert diag["event"] == "DTR_EXIT20"
    assert diag["current_error"] is False
    assert diag["current_status"] == "WAITING_HUMAN"
    assert diag["unresolved_resumed_count"] == 1
    assert diag["unresolved_resumed"][0] == {
        "run_id": old.run_id,
        "status": "WAITING_HUMAN",
        "error_present": True,
    }
    assert "SECRET_NEVERSHOW" not in json.dumps(diag)
    assert "PRIVATE_CUSTOMER" not in json.dumps(diag)
    assert "NEVER_PRINT" not in json.dumps(diag)


def test_current_failure_never_disappears_when_previous_runs_clean(capsys):
    now = _run(23, "WAITING_HUMAN", "sensitive live source text")
    assert _exit_code_with_diagnostic([_run(21)], now) == 20
    raw = capsys.readouterr().err
    assert json.loads(raw)["current_error"] is True
    assert "sensitive live source text" not in raw


def test_untrusted_status_and_id_are_redacted(capsys):
    unsafe = SimpleNamespace(
        run_id="https://private.example/secret",
        status="FAILED token=ABC",
        error_summary="PWD PRIVATE",
    )
    assert _exit_code_with_diagnostic([unsafe], _run(23)) == 20
    d = json.loads(capsys.readouterr().err)
    assert d["unresolved_resumed"][0]["run_id"] == "REDACTED"
    assert d["unresolved_resumed"][0]["status"] == "REDACTED"
    assert "PRIVATE" not in json.dumps(d)


def test_many_historical_errors_are_bounded(capsys):
    past = [_run(i, error="PRIVATE") for i in range(1, 18)]
    assert _exit_code_with_diagnostic(past, _run(23)) == 20
    d = json.loads(capsys.readouterr().err)
    assert d["unresolved_resumed_count"] == 17
    assert len(d["unresolved_resumed"]) == 8
    assert d["unresolved_resumed_truncated"] == 9


def test_bad_status_without_error_summary_still_fails_closed(capsys):
    assert _exit_code_with_diagnostic(
        [], _run(23, "FAILED")
    ) == 20
    assert json.loads(capsys.readouterr().err)["current_error"] is True
