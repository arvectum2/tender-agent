from datetime import UTC, datetime, timedelta

import pytest

from src.modules.ops_observability import analysis_window as window
from src.tender_research.models import TenderAnalysisJob

NOW = datetime(2026, 11, 17, 8, tzinfo=UTC)


def add(session, status='completed', seconds=60, *, finished=NOW-timedelta(minutes=1), kind='analyze', invalid=False):
    base = finished or NOW-timedelta(minutes=1)
    session.add(TenderAnalysisJob(job_type=kind, registry_number='synthetic', status=status,
        created_at=base-timedelta(seconds=seconds), started_at=base+timedelta(seconds=1) if invalid else base-timedelta(seconds=seconds/2),
        finished_at=finished, updated_at=base))


def test_empty_is_not_pass(session):
    snapshot = window.measure_analysis_window(session, now=NOW)
    assert snapshot['state'] == 'NO_OBSERVATIONS'
    assert snapshot['clean_completion_rate'] is None
    assert snapshot['queue_to_finished_seconds']['p95'] is None
    assert snapshot['rolling_production_slo_approved'] is False


def test_only_terminal_analysis_rows_half_open_window(session):
    add(session, seconds=60)
    add(session, 'completed_with_warnings', 120)
    add(session, 'failed')
    add(session, 'cancelled')
    add(session, kind='prepare')
    add(session, finished=NOW)
    add(session, finished=NOW-timedelta(days=7, seconds=1))
    add(session, finished=NOW-timedelta(days=7), seconds=90)
    session.commit()
    out = window.measure_analysis_window(session, now=NOW)
    assert out['terminal_jobs'] == 5
    assert out['outcomes'] == {'completed': 2, 'completed_with_warnings': 1, 'failed': 1, 'cancelled': 1}
    assert out['clean_completion_rate'] == .4
    assert out['queue_to_finished_seconds']['sample_count'] == 3
    assert out['queue_to_finished_seconds']['p50'] == 90
    assert out['queue_to_finished_seconds']['p95'] == 120
    assert out['state'] == 'INSUFFICIENT_LATENCY_SAMPLE'


def test_missing_and_invalid_times_not_successfully_measured(session):
    add(session, invalid=True)
    add(session, finished=None)
    session.commit()
    out = window.measure_analysis_window(session, now=NOW)
    assert out['terminal_rows_missing_finish_recently_updated'] == 1
    assert out['completed_jobs_invalid_timing'] == 1
    assert out['queue_to_finished_seconds']['p95'] is None
    assert out['state'] == 'INCOMPLETE_TIMING_EVIDENCE'


def test_sample_floor_never_approves_slo(session):
    for i in range(1, 101):
        add(session, seconds=i)
    session.commit()
    out = window.measure_analysis_window(session, now=NOW)
    assert out['state'] == 'OBSERVED_NOT_APPROVED'
    assert out['queue_to_finished_seconds']['p95'] == 95
    assert not out['rolling_production_slo_approved']
    assert out['full_ingestion_to_report_latency'] is None


def test_bounded_query_refuses_truncated_aggregate(session, monkeypatch):
    monkeypatch.setattr(window, 'MAX_ROWS', 1)
    add(session)
    add(session)
    session.commit()
    out = window.measure_analysis_window(session, now=NOW)
    assert out['state'] == 'ROW_LIMIT_EXCEEDED'
    assert out['terminal_jobs'] is None and out['clean_completion_rate'] is None
    assert all(v is None for v in out['outcomes'].values())


@pytest.mark.parametrize('days', [0, 31, True, 1.5])
def test_invalid_window(session, days):
    with pytest.raises(ValueError):
        window.measure_analysis_window(session, now=NOW, days=days)


def test_only_missing_finished_rows_are_incomplete_not_empty(session):
    add(session, finished=None)
    session.commit()
    out = window.measure_analysis_window(session, now=NOW)
    assert out['state'] == 'INCOMPLETE_TIMING_EVIDENCE'
    assert out['terminal_jobs'] == 0
    assert out['terminal_rows_missing_finish_recently_updated'] == 1
    assert out['clean_completion_rate'] is None
