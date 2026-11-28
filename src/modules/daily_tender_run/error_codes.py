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


_PREPARATION_REASONS = frozenset({
    "tender_missing", "original_verification_failed", "projection_failed",
    "metadata_missing", "originals_missing", "text_missing", "projection_empty",
    "index_pending", "index_incomplete",
})


class PreparationNotReady(RuntimeError):
    """Carry a bounded reason, never upstream error strings or signed URLs."""

    def __init__(self, prepared: object):
        reason = "failure"
        steps = getattr(prepared, "steps", None)
        states = {
            (getattr(step, "name", None), getattr(step, "status", None))
            for step in steps
            if type(getattr(step, "name", None)) is str
            and type(getattr(step, "status", None)) is str
        } if isinstance(steps, (tuple, list)) else set()
        if getattr(prepared, "status", None) == "no_tender":
            reason = "tender_missing"
        elif ("verify_originals", "failed") in states:
            reason = "original_verification_failed"
        elif ("extract_text", "failed") in states:
            reason = "projection_failed"
        elif ("build_embeddings", "pending") in states or ("readiness_check", "pending") in states:
            reason = "index_pending"
        elif ("readiness_check", "failed") in states:
            counts = [getattr(prepared, name, None) for name in (
                "documents_total", "documents_downloaded", "extracted_texts_total", "chunks_total",
            )]
            if all(type(count) is int and count >= 0 for count in counts):
                total, downloaded, extracted, chunks = counts
                if chunks:
                    reason = "index_incomplete"
                elif not total:
                    reason = "metadata_missing"
                elif not downloaded:
                    reason = "originals_missing"
                elif not extracted:
                    reason = "text_missing"
                else:
                    reason = "projection_empty"
        self.reason = reason
        super().__init__(reason)


def safe_processing_error(stage: str, exc: Exception) -> str:
    """Store only stage/type diagnostics; upstream errors may include signed EIS URLs.

    This code is returned through the DTR API and persisted in the database;
    exception messages must never cross this boundary, even when truncated.
    """
    phase = _FAILURE_PHASES.get(stage, "processing_failed")
    name = type(exc).__name__
    if stage == "INDEX_DATA_PLATFORM" and isinstance(exc, PreparationNotReady):
        reason = exc.reason if isinstance(exc.reason, str) and exc.reason in _PREPARATION_REASONS else "failure"
    elif isinstance(exc, TimeoutError) or name in _TIMEOUT_NAMES:
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
            and (parts[1] in _VISIBLE_REASONS or (
                parts[0] == "source_or_index_not_ready" and parts[1] in _PREPARATION_REASONS
            ))
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
