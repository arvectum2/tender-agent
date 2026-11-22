"""Safe, stable DTR failure codes for persistent and API-visible diagnostics."""
from __future__ import annotations

_FAILURE_PHASES = {
    "ACQUIRE_DOCS": "source_acquisition_failed",
    "INDEX_DATA_PLATFORM": "source_or_index_not_ready",
    "ANALYZE": "analysis_failed",
    "SUMMARIZE": "manager_summary_failed",
    "POST_DECISION": "post_decision_failed",
}
_TIMEOUT_NAMES = {"ReadTimeout", "ConnectTimeout", "Timeout", "TimeoutException"}
_CONNECTION_NAMES = {"ConnectError", "ConnectionError"}


def safe_processing_error(stage: str, exc: Exception) -> str:
    """Store only stage/type diagnostics; upstream errors may include signed EIS URLs.

    This code is returned through the DTR API and persisted in the database;
    exception messages must never cross this boundary, even when truncated.
    """
    phase = _FAILURE_PHASES.get(stage, "processing_failed")
    name = type(exc).__name__
    if isinstance(exc, TimeoutError) or name in _TIMEOUT_NAMES:
        reason = "timeout"
    elif isinstance(exc, ConnectionError) or name in _CONNECTION_NAMES:
        reason = "connection_unavailable"
    elif isinstance(exc, OSError):
        reason = "io_failure"
    elif isinstance(exc, ValueError):
        reason = "invalid_input"
    else:
        reason = "failure"
    return f"{phase}:{reason}"
