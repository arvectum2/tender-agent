"""Bounded read-only analysis job snapshot; not immutable events or production SLO."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.ops_observability.service import _as_utc
from src.tender_research.models import TenderAnalysisJob

OUTCOMES = ('completed', 'completed_with_warnings', 'failed', 'cancelled')
MAX_ROWS = 10_000
MIN_LATENCY_SAMPLE = 100  # proposed monitoring floor, not owner-approved SLO


def _percentile(values, p):
    return round(sorted(values)[math.ceil(len(values) * p) - 1], 3) if values else None


def measure_analysis_window(session: Session, *, now: datetime, days: int = 7) -> dict:
    """Read current terminal job rows, not retries, human decisions or full ingestion timings.

    No tenant identifiers or report content returned. Caller must authorize its own
    database access; deliberately not exposed through an unauthenticated endpoint.
    """
    if now.tzinfo is None or now.utcoffset() is None or type(days) is not int or not 1 <= days <= 30:
        raise ValueError('Explicit aware time and 1..30 day window required')
    end = now.astimezone(UTC)
    start = end - timedelta(days=days)
    job = TenderAnalysisJob
    base = (job.job_type == 'analyze', job.status.in_(OUTCOMES))
    rows = session.execute(select(job.status, job.created_at, job.started_at, job.finished_at).where(
        *base, job.finished_at >= start, job.finished_at < end
    ).limit(MAX_ROWS + 1)).all()
    # Missing finish time is separately visible, not counted as a completed event.
    missing = int(session.scalar(select(func.count()).select_from(job).where(
        *base, job.finished_at.is_(None), job.updated_at >= start, job.updated_at < end)) or 0)
    counts = dict.fromkeys(OUTCOMES, 0)
    durations = []
    invalid = 0
    overflow = len(rows) > MAX_ROWS
    if not overflow:
        for status, created, started, finished in rows:
            counts[status] += 1
            if status not in ('completed', 'completed_with_warnings'):
                continue
            created, started, finished = map(_as_utc, (created, started, finished))
            if created is None or started is None or finished is None or not created <= started <= finished:
                invalid += 1
                continue
            durations.append((finished - created).total_seconds())
    total = len(rows) if not overflow else None
    sample = len(durations) if not overflow else None
    state = ('ROW_LIMIT_EXCEEDED' if overflow else 'INCOMPLETE_TIMING_EVIDENCE' if missing or invalid else
             'NO_OBSERVATIONS' if not rows else
             'INSUFFICIENT_LATENCY_SAMPLE' if len(durations) < MIN_LATENCY_SAMPLE else 'OBSERVED_NOT_APPROVED')
    return {'schema': 'apr07_analysis_job_window_v1', 'scope': 'CURRENT_TERMINAL_ANALYSIS_JOB_ROWS_NOT_EVENT_LOG',
            'window_start_utc': start.isoformat(), 'window_end_exclusive_utc': end.isoformat(),
            'state': state, 'terminal_jobs': total, 'outcomes': counts if not overflow else dict.fromkeys(OUTCOMES),
            'terminal_rows_missing_finish_recently_updated': missing,
            'completed_jobs_invalid_timing': invalid if not overflow else None,
            'clean_completion_rate': round(counts['completed'] / total, 6) if total else None,
            'queue_to_finished_seconds': {'sample_count': sample,
                'p50': _percentile(durations, .5), 'p95': _percentile(durations, .95),
                'minimum_sample_proposed': MIN_LATENCY_SAMPLE},
            'operator_time_to_decision': None, 'full_ingestion_to_report_latency': None,
            'rolling_production_slo_approved': False, 'model_promotion_authorized': False}
