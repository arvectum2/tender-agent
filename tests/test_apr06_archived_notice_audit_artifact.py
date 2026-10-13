"""Regression contract for the immutable archived-notice EIS receipt summary."""
from __future__ import annotations

import json
from pathlib import Path

REPORT = (Path(__file__).resolve().parents[1]
          / "docs/acceptance/apr06_archived_notice_binding_2026-10-13.json")


def _report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_real_archived_20_cases_no_source_or_human_promotion():
    data = _report()
    assert data["schema_version"] == "apr06-archived-notice-source-binding-v1"
    assert data["summary"]["cases"] == 20
    assert data["summary"]["cases_with_archived_notices"] == 17
    assert data["summary"]["archived_latest_attachment_count"] == 77
    assert data["summary"]["archived_latest_name_size_correlations"] == 50
    assert data["summary"]["archived_latest_unmatched"] == 27
    assert data["summary"]["states"] == {
        "ARCHIVED_LATEST_ATTACHMENTS_INCOMPLETE": 7,
        "ARCHIVED_NAME_SIZE_ONLY_CORRELATION": 9,
        "DEADLINE_UNKNOWN_FROM_ARCHIVED_NOTICE": 1,
        "NO_ARCHIVED_NOTICE": 3,
    }
    assert data["official_current_eis_verified"] == 0
    assert data["human_gold_labels"] == 0
    assert data["commercial_accepted"] is False
    assert data["notice_uid_or_attachment_version_link_verified"] is False
    assert all(c["official_current_eis_status_verified"] is False
               and c["official_attachment_uid_bound"] is False
               and c["human_reviewed"] is False
               and c["commercial_go"] is False
               for c in data["cases"])


def test_regressions_on_two_changed_notices_and_missing_attachment():
    cases = {c["reg_number"]: c for c in _report()["cases"]}
    aksay = cases["0158300034526000388"]
    assert aksay["archived_notice_revisions"] == [1, 2, 3, 4, 5]
    assert aksay["latest_archived_notice_version"] == 5
    assert aksay["latest_archived_deadline"] == "2026-10-12T08:00:00+03:00"

    czn = cases["0348100024426000039"]
    assert czn["archived_notice_revisions"] == [1, 2, 3]
    assert czn["latest_archived_deadline"] == "2026-10-19T10:00:00+03:00"
    assert czn["latest_notice_attachment_count"] == 7
    assert czn["archive_name_size_unmatched"] == 1
    assert czn["source_state"] == "ARCHIVED_LATEST_ATTACHMENTS_INCOMPLETE"


def test_zero_source_and_unknown_deadline_never_pass():
    cases = {c["reg_number"]: c for c in _report()["cases"]}
    for reg in ("0348100024426000052", "0148300050426000047",
                "0318200087026000163"):
        assert cases[reg]["source_state"] == "NO_ARCHIVED_NOTICE"
        assert cases[reg]["latest_archived_notice_version"] is None
    assert (cases["0349500000226000003"]["source_state"]
            == "DEADLINE_UNKNOWN_FROM_ARCHIVED_NOTICE")
    assert len(cases) == 20
