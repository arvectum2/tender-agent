"""Regression gates for AI-only APR-06 screening without synthetic expert gold."""
from __future__ import annotations

import copy
import json
from datetime import datetime

import pytest

from scripts.acceptance.apr06_ai_provisional_review import (
    CANDIDATES,
    PREFILL,
    PRIOR_AUDIT,
    build_review,
)

AS_OF = datetime.fromisoformat("2026-10-13T12:33:00+03:00")


def _sources():
    return (
        json.loads(CANDIDATES.read_text(encoding="utf-8")),
        json.loads(PRIOR_AUDIT.read_text(encoding="utf-8")),
        json.loads(PREFILL.read_text(encoding="utf-8")),
    )


def test_all_28_are_accounted_for_without_human_or_live_source_claims():
    review = build_review(*_sources(), as_of=AS_OF)
    assert review["schema_version"] == "apr06-ai-provisional-asof-v1"
    assert review["summary"] == {
        "candidate_ids": 28,
        "prior_source_read_ai_cases": 9,
        "no_prior_primary_source_review": 19,
        "archived_deadlines_passed_as_of_date": 7,
        "archived_deadlines_future_as_of_date": 2,
        "prior_partial_text_extraction_cases": 1,
        "live_eis_verified_cases_today": 0,
        "actual_human_gold_cases": 0,
        "kpi_acceptance": "NOT_MEASURED",
    }
    assert review["authority"]["commercial_acceptance"] is False
    assert review["authority"]["human_signed_decisions"] == 0
    assert len({case["reg_number"] for case in review["cases"]}) == 28
    assert all(not case["commercial_go"] and not case["human_reviewed"]
               and not case["bid_or_payment_authorized"]
               and not case["current_eis_status_verified"]
               for case in review["cases"])


def test_aksay_stale_machine_no_go_is_not_reused_as_current_bid_advice():
    review = build_review(*_sources(), as_of=AS_OF)
    cases = {c["reg_number"]: c for c in review["cases"]}
    aksay = cases["0158300034526000388"]
    assert aksay["previous_machine_decision"] == "NO_GO"
    assert aksay["archived_notice"]["revision"] == 5
    assert aksay["archived_notice"]["deadline"] == "2026-10-12T08:00:00+03:00"
    assert aksay["archive_deadline_status"] == "ARCHIVED_DEADLINE_PASSED"
    assert aksay["advisory"] == "NO_ACTION_ON_EXPIRED_ARCHIVED_DEADLINE_RECHECK_LIVE_EIS"
    assert aksay["previous_audit_comparison"] == "INVALID_HARD_NO_GO_STALE_NOTICE_REVISION"


def test_museum_and_employment_center_are_defer_pending_current_source():
    cases = {c["reg_number"]: c for c in build_review(*_sources(), as_of=AS_OF)["cases"]}
    for number in ("0372200172326000015", "0348100024426000039"):
        case = cases[number]
        assert case["archive_deadline_status"] == "ARCHIVED_DEADLINE_IN_FUTURE"
        assert case["advisory"] == "DEFER_RECHECK_LIVE_EIS_AND_SPECIFICATIONS"
    assert cases["0348100024426000039"]["previously_text_available_files"] == 10
    assert cases["0348100024426000039"]["archived_source_files"] == 19
    assert cases["0348100024426000039"]["archived_notice"]["revision"] == 3


def test_aggregator_only_cases_never_receive_fabricated_document_judgments():
    review = build_review(*_sources(), as_of=AS_OF)
    cases = [c for c in review["cases"]
             if c["evidence_tier"] == "AGGREGATOR_CANDIDATE_NO_ORIGINALS_IN_THIS_AUDIT"]
    assert len(cases) == 19
    assert all(c["advisory"] == "DEFER_INSUFFICIENT_PRIMARY_EIS_EVIDENCE"
               and c["independent_document_review"] == "NOT_PERFORMED"
               and c["archive_deadline_status"] == "NOT_MEASURED"
               and "archived_notice" not in c for c in cases)


def test_unknown_or_promoted_source_is_rejected():
    manifest, audit, prefill = _sources()
    manifest["cases"][0]["verification"]["state"] = "eis_verified"
    with pytest.raises(ValueError, match="Unexpected verified"):
        build_review(manifest, audit, prefill, as_of=AS_OF)


def test_no_duplicate_or_foreign_cases_may_inflate_denominators():
    manifest, audit, prefill = _sources()
    manifest["cases"].append(copy.deepcopy(manifest["cases"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        build_review(manifest, audit, prefill, as_of=AS_OF)
    manifest, audit, prefill = _sources()
    audit["cases"][0]["reg_number"] = "9999999999999999999"
    with pytest.raises(ValueError, match="outside current manifest"):
        build_review(manifest, audit, prefill, as_of=AS_OF)


def test_never_promote_ai_source_to_human_approved_gold():
    manifest, audit, prefill = _sources()
    audit["human_signed_decisions"] = 1
    with pytest.raises(ValueError, match="independent human truth"):
        build_review(manifest, audit, prefill, as_of=AS_OF)
    manifest, audit, prefill = _sources()
    audit["cases"][0]["human_confirmed"] = True
    with pytest.raises(ValueError, match="human/action separation"):
        build_review(manifest, audit, prefill, as_of=AS_OF)
    manifest, audit, prefill = _sources()
    prefill["cases"][0]["human_reviewed"] = True
    with pytest.raises(ValueError, match="independent human review"):
        build_review(manifest, audit, prefill, as_of=AS_OF)


def test_recorded_digest_must_be_well_formed_but_is_not_rehashed():
    manifest, audit, prefill = _sources()
    audit["cases"][0]["latest_archived_notice"]["source_sha256"] = "0" * 63
    with pytest.raises(ValueError, match="digest syntax"):
        build_review(manifest, audit, prefill, as_of=AS_OF)


def test_reject_naive_datetime_and_asof_time_propagates():
    manifest, audit, prefill = _sources()
    with pytest.raises(ValueError, match="UTC offset"):
        build_review(manifest, audit, prefill, as_of=datetime(2026, 10, 13))
    as_of = datetime.fromisoformat("2026-10-09T07:00:00+03:00")
    review = build_review(manifest, audit, prefill, as_of=as_of)
    assert review["summary"]["archived_deadlines_passed_as_of_date"] == 6
    assert review["summary"]["archived_deadlines_future_as_of_date"] == 3


def test_checked_in_asof_artifact_is_bitwise_reproducible_from_input():
    from scripts.acceptance.apr06_ai_provisional_review import SOURCES

    persisted = json.loads(
        (SOURCES / "apr06_ai_provisional_asof_2026-10-13.json").read_text(encoding="utf-8")
    )
    assert persisted == build_review(*_sources(), as_of=AS_OF)
    assert persisted["provenance"]["source_hashes_recomputed"] == 0
    assert persisted["provenance"]["new_primary_bytes_verified"] == 0
