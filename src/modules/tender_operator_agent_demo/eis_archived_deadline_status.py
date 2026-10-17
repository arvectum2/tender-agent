"""Timeline proof from original archived EIS notice, not live legal status.

The v1 notice endDT is a verifiable historical fact. After that clock time
passes, it is unsafe to infer that the source has never been amended or
the legal procedure is canceled, awarded, or accepting an application.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_STATUS = "original_archived_notice_deadline_observation_v1"


def archived_notice_deadline_observation(
    fact: dict[str, Any] | None, *, as_of: datetime | None = None
) -> dict[str, Any]:
    """No IO or external actions; fail closed on unproved/timezone-free dates."""
    now = as_of if as_of is not None else datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    now = now.astimezone(UTC)
    result: dict[str, Any] = {
        "contract": _STATUS,
        "as_of_utc": now.isoformat(),
        "source_fact_status": "UNKNOWN",
        "archived_deadline": None,
        "relation_to_archived_deadline": "UNKNOWN",
        "current_public_eis_procedure_status": "UNKNOWN",
        "current_public_notice_revision_verified": False,
        "live_submission_eligibility_verified": False,
        "authorized_to_submit": False,
        "final_protocol_or_award_verified": False,
    }
    if (
        not isinstance(fact, dict)
        or fact.get("status") != "KNOWN"
        or not isinstance(fact.get("evidence"), list)
        or len(fact["evidence"]) != 1
        or not isinstance(fact["evidence"][0], dict)
        or fact["evidence"][0].get("locator") != "XML:endDT"
        or not isinstance(fact["evidence"][0].get("file_id"), str)
        or fact["evidence"][0].get("source_ref") != (
            "eis-xml:" + fact["evidence"][0]["file_id"] + ":endDT"
        )
        or not isinstance(fact.get("value"), str)
    ):
        return result
    raw = fact["value"]
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return result
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return result
    if len(raw) > 64:
        return result
    result["source_fact_status"] = "KNOWN"
    result["archived_deadline"] = parsed.isoformat()
    result["relation_to_archived_deadline"] = (
        "ARCHIVED_CUTOFF_REACHED" if now >= parsed else "ARCHIVED_CUTOFF_NOT_YET_REACHED"
    )
    return result
