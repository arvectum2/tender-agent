"""Current clock vs archived official EIS endDT, without live procedure claims."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.tender_operator_agent_demo.eis_archived_deadline_status import (
    archived_notice_deadline_observation,
)

DEADLINE = "2026-10-16T10:00:00+03:00"


def source(value=DEADLINE):
    return {
        "status": "KNOWN", "value": value,
        "evidence": [{
            "file_id": "FILE-01",
            "locator": "XML:endDT",
            "source_ref": "eis-xml:FILE-01:endDT",
        }],
    }


@pytest.mark.parametrize(("observed", "expected"), [
    (datetime(2026, 10, 16, 6, 59, tzinfo=UTC), "ARCHIVED_CUTOFF_NOT_YET_REACHED"),
    (datetime(2026, 10, 16, 7, tzinfo=UTC), "ARCHIVED_CUTOFF_REACHED"),
    (datetime(2026, 10, 17, 9, 20, tzinfo=UTC), "ARCHIVED_CUTOFF_REACHED"),
])
def test_archive_cutoff_boundary_has_no_claim_of_live_eligibility(observed, expected):
    result = archived_notice_deadline_observation(source(), as_of=observed)
    assert result["source_fact_status"] == "KNOWN"
    assert result["archived_deadline"] == DEADLINE
    assert result["relation_to_archived_deadline"] == expected
    assert result["current_public_eis_procedure_status"] == "UNKNOWN"
    assert result["current_public_notice_revision_verified"] is False
    assert result["live_submission_eligibility_verified"] is False
    assert result["authorized_to_submit"] is False
    assert result["final_protocol_or_award_verified"] is False


@pytest.mark.parametrize("bad", [
    None, {}, {"value": DEADLINE},
    {"status": "KNOWN", "value": DEADLINE, "evidence": []},
    {"status": "KNOWN", "value": DEADLINE, "evidence": [
        {"locator": "XML:endDT"}, {"locator": "XML:endDT"}]},
    {"status": "KNOWN", "value": DEADLINE, "evidence": [{"locator": "XML:unknown"}]},
    {"status": "KNOWN", "value": DEADLINE,
     "evidence": [{"locator": "XML:endDT", "source_ref": "eis-xml:FILE-01:endDT"}]},
    {"status": "KNOWN", "value": DEADLINE,
     "evidence": [{"locator": "XML:endDT", "file_id": "FILE-01", "source_ref": "forged"}]},
    {"status": "KNOWN", "value": DEADLINE,
     "evidence": ["unsafe-data"]},
    source("2026-10-16T10:00:00"),
    source("this-is-not-a-date"),
    source("2026-10-16T10:00:00+03:00" + "x" * 80),
])
def test_missing_or_ambiguous_fact_never_produces_submission_status(bad):
    result = archived_notice_deadline_observation(
        bad, as_of=datetime(2026, 10, 17, tzinfo=UTC)
    )
    assert result["relation_to_archived_deadline"] == "UNKNOWN"
    assert result["archived_deadline"] is None
    assert result["authorized_to_submit"] is False


def test_fails_closed_for_naive_as_of():
    with pytest.raises(ValueError):
        archived_notice_deadline_observation(source(), as_of=datetime(2026, 10, 17))  # noqa: DTZ001  # negative test


def test_timezone_equivalence():
    source_fact = source("2026-10-16T09:00:00+02:00")
    result = archived_notice_deadline_observation(
        source_fact, as_of=datetime(2026, 10, 16, 10, tzinfo=UTC)
    )
    assert result["relation_to_archived_deadline"] == "ARCHIVED_CUTOFF_REACHED"
    assert not result["final_protocol_or_award_verified"]


def test_does_not_promote_unknown_from_missing_extracted_evidence():
    result = archived_notice_deadline_observation({
        "status": "UNKNOWN", "value": DEADLINE,
        "evidence": [{"locator": "XML:endDT"}],
    }, as_of=datetime.now(UTC) + timedelta(days=1))
    assert result["relation_to_archived_deadline"] == "UNKNOWN"
