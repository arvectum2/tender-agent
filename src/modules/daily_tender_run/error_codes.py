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


# Legacy failures may contain signed URLs or arbitrary network exception bodies.
# The historical rows are preserved for audit; only read-model fields are masked.
_VISIBLE_PHASES = {*_FAILURE_PHASES.values(), "processing_failed"}
_VISIBLE_REASONS = {
    "timeout", "connection_unavailable", "io_failure", "invalid_input", "failure",
    "legacy_error_redacted",
}


def public_failure_code(value: object, *, post_decision: bool = False) -> str | None:
    """Allow only our own exact stable codes in API-visible error fields."""
    if value is None:
        return None
    if isinstance(value, str):
        parts = value.split(":")
        if (
            len(parts) == 2
            and parts[0] in _VISIBLE_PHASES
            and parts[1] in _VISIBLE_REASONS
        ):
            return value
    phase = "post_decision_failed" if post_decision else "processing_failed"
    return f"{phase}:legacy_error_redacted"


def public_post_decision_state(value: object) -> dict:
    """Mask historical last_error without mutating SQLAlchemy's JSON value."""
    if not isinstance(value, dict):
        return {}
    result = dict(value)
    if "last_error" in result:
        original = result["last_error"]
        code = public_failure_code(
            original.get("code") if isinstance(original, dict) else None,
            post_decision=True,
        ) or "post_decision_failed:legacy_error_redacted"
        # The legacy record may contain a secret in type/message/other keys.
        result["last_error"] = {"type": "redacted", "code": code, "message": code}
    return result


def public_discovery_error_summary(value: object) -> str | None:
    """Old free-text discovery errors can expose search parameters; mask them."""
    return "discovery_incomplete:details_redacted" if value else None
