"""Adversarial audit of frozen, previously produced development results only."""
from __future__ import annotations

import json

import pytest

from scripts.quality.apr067_corrected_cohort_integrity import (
    CORRECTED_PATH,
    ORIGINAL_PATH,
    CohortIntegrityError,
    _parse,
    audit,
)


def sources():
    return ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes()


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode()


def test_real_frozen_source_pair_unchanged_and_explicitly_not_legal_gold():
    old, new = sources()
    result = audit(old, new)
    assert result["distinct_archived_original_case_ids"] == 20
    assert result["model_provider_calls_recorded"] == 80
    assert result["original_file_sha_records"] == 210
    assert result["critical_eis_xml_citation_records"] == 60
    assert result["source_only_semantic_corrections"] == ["0349100009326000005"]
    assert result["new_llm_calls_for_source_correction"] == 0
    assert result["model_only_seconds"]["median"] == 351.655
    assert result["model_only_seconds"]["p90_nearest_rank"] == 389.27
    assert result["true_operator_time_to_decision"] is None
    assert result["rolling_production_slo"] is None
    assert result["independent_legal_human_gold"] is None
    assert result["current_official_eis_revision_verified"] is False
    assert result["commercial_bid_go"] is False


def test_tracked_frozen_bytes_require_exact_independent_pin():
    old, new = sources()
    amended = new + b" "
    with pytest.raises(CohortIntegrityError, match="frozen cohort bytes changed"):
        audit(old, amended)
    with pytest.raises(CohortIntegrityError, match="frozen cohort bytes changed"):
        audit(old + b" ", new)


def update_pair(mutate_old=None, mutate_corrected=None):
    old, new = [json.loads(raw) for raw in sources()]
    if mutate_old is not None:
        mutate_old(old)
    if mutate_corrected is not None:
        mutate_corrected(new)
    return encode(old), encode(new)


@pytest.mark.parametrize(("name", "mutator"), [
    ("fake_full_acceptance", lambda d: d.update(development_semantically_accepted_report_count=21)),
    ("mismatch_80_model_calls", lambda d: d["cases"][3].update(gemma4_local_llm_calls=5)),
    ("relabel_second_case", lambda d: d["cases"][1].update(registry_number=d["cases"][0]["registry_number"])),
    ("fake_evidence_files", lambda d: d.update(original_firstparty_sha_file_count=211)),
    ("fake_citations", lambda d: d["cases"][0].update(original_eis_xml_critical_source_citations=4)),
    ("false_time", lambda d: d["cases"][0].update(model_only_seconds=-5)),
    ("wrong_p90", lambda d: d["local_model_analysis_only_seconds"].update(p90_nearest_rank=888.88)),
    ("wrong_total", lambda d: d["local_model_analysis_only_seconds"].update(total=123)),
    ("missing_workflow_caveat", lambda d: d.update(not_measured=["unrelated"])),
    ("false_provenance_llm", lambda d: d["source_correction_provenance"].update(new_model_calls=4)),
    ("wrong_source_sha", lambda d: d["source_correction_provenance"].update(original_prior_19_20_cohort_sha256="0"*64)),
    ("fake_original_report_hash", lambda d: d["source_correction_provenance"].update(original_report_json_sha256="broken")),
    ("second_case_changed", lambda d: d["cases"][5].update(status="fabricated_source_acceptance")),
    ("fake_source_note", lambda d: d.update(actual_original_eis_xml_critical_fact_citations=999)),
])
def test_corrected_source_mutation_rejected_even_without_pin(name, mutator):
    original, corrected = update_pair(mutate_corrected=mutator)
    with pytest.raises(CohortIntegrityError):
        audit(original, corrected, check_pins=False)


def test_original_semantic_history_cannot_silently_be_promoted():
    original, corrected = update_pair(
        mutate_old=lambda d: d["cases"][12].update(development_semantic_report_accepted=True),
    )
    with pytest.raises(CohortIntegrityError):
        audit(original, corrected, check_pins=False)


def test_original_historical_case_count_does_not_permit_dropped_row():
    original, corrected = update_pair(mutate_old=lambda d: d["cases"].pop())
    with pytest.raises(CohortIntegrityError):
        audit(original, corrected, check_pins=False)


def test_correction_does_not_authorize_rewriting_old_model_times_in_both_snapshots():
    original, corrected = sources()
    old, new = json.loads(original), json.loads(corrected)
    old["cases"][12]["model_only_seconds"] = 999
    new["cases"][12]["model_only_seconds"] = 999
    with pytest.raises(CohortIntegrityError):
        audit(encode(old), encode(new))


@pytest.mark.parametrize("bad", [
    b'{"cases": [], "cases": []}', b'not-json', b'null', b'[]', b'',
])
def test_malformed_source_json_or_duplicate_keys_fail_closed(bad):
    with pytest.raises(CohortIntegrityError):
        _parse(bad)


def test_true_source_snapshot_bytes_stay_untouched_by_validation():
    original, corrected = sources()
    assert audit(original, corrected)["distinct_archived_original_case_ids"] == 20
    assert sources() == (original, corrected)
