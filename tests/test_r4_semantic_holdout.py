"""Blind semantic holdout registration, using deliberately fake source IDs."""
from __future__ import annotations

import copy
import hashlib

import pytest

from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    HoldoutLeakageError,
    forbidden_development_sources,
    lock_unseen_real_cohort,
    semantic_metrics_or_not_measured,
    verify_cohort_lock,
)

T0 = "2026-10-14T20:00:00+00:00"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def baseline():
    numbers = [f"{i:019d}" for i in range(1, 21)]
    return {
        "competitive_notices": [
            {"registry_number": n, "original_zip_sha256": sha("ZIP"+n),
             "original_xml_sha256": sha("XML"+n)} for n in numbers
        ],
        "selected_original_notice_attachment_coverage": {
            "cases": [
                {"registry_number": n, "documents": [
                    {"original_document_sha256": sha(f"DOC-{n}-{j}")}
                    for j in range(3)
                ]} for n in numbers
            ]
        },
    }


def clean_candidate(number: str = "9000000000000000001"):
    return {
        "registry_number": number,
        "attestation": "VERIFIED_OFFICIAL_GETDOCSIP_XML_AND_BINARY",
        "source_document_stage": "PRE_LABEL_PRE_SUT",
        "official_zip_sha256": sha("NOVEL ZIP" + number),
        "official_xml_sha256": sha("NOVEL XML" + number),
        "binary_original_sha256": [sha("NOVEL SOURCE"+number)],
    }


def make_lock(candidates=None, forbidden=None):
    return lock_unseen_real_cohort(
        [clean_candidate()] if candidates is None else candidates,
        forbidden=forbidden_development_sources(baseline()) if forbidden is None else forbidden,
        source_set_id="holdout_20261014_R4",
        locked_at_utc=T0,
    )


def test_first_party_source_only_holdout_pins_provenance_not_gold():
    lock = make_lock()
    assert lock["case_count"] == 1
    assert lock["gold_freeze_status"] == "PENDING_INDEPENDENT_EXPERT"
    assert not lock["sut_run_authorized"]
    assert lock["semantic_precision"] is None and lock["semantic_recall"] is None
    assert lock["immutable_lock_sha256"]
    verify_cohort_lock(lock)
    result = semantic_metrics_or_not_measured(
        holdout_lock=lock, human_gold_freeze_receipt=None, sut_run_receipt=None,
    )
    assert result["status"] == "NOT_MEASURED"
    assert result["precision"] is None and result["recall"] is None
    assert not result["bid_ready"]


def test_cohort_is_order_independent_but_its_identity_is_frozen():
    first = clean_candidate("9000000000000000002")
    second = clean_candidate("9000000000000000003")
    a = make_lock([first, second])
    b = make_lock([second, first])
    assert a == b
    changed = copy.deepcopy(a)
    changed["cases"][0]["registry_number"] = "9000000000000000007"
    with pytest.raises(HoldoutLeakageError, match="edited"):
        verify_cohort_lock(changed)
    with pytest.raises(HoldoutLeakageError, match="Duplicate"):
        make_lock([first, first])


@pytest.mark.parametrize("mutate", [
    lambda c, f: c.update(registry_number=next(iter(f["notice_numbers"]))),
    lambda c, f: c.update(official_xml_sha256=next(iter(f["xml_sha256"]))),
    lambda c, f: c.update(official_zip_sha256=next(iter(f["zip_sha256"]))),
    lambda c, f: c.update(binary_original_sha256=[next(iter(f["binary_sha256"]))]),
    lambda c, f: c.update(attestation="UNVERIFIED"),
    lambda c, f: c.update(source_document_stage="SUT_ALREADY_SEEN"),
    lambda c, f: c.update(binary_original_sha256=[]),
    lambda c, f: c.update(official_xml_sha256="unknown"),
    lambda c, f: c.update(registry_number="BAD"),
])
def test_previously_seen_or_unverified_source_cannot_be_called_holdout(mutate):
    f = forbidden_development_sources(baseline())
    case = clean_candidate()
    mutate(case, f)
    with pytest.raises((ValueError, HoldoutLeakageError)):
        make_lock([case], forbidden=f)


def test_repeated_attachment_sha_across_two_cases_invalidates_holdout():
    first = clean_candidate("9000000000000000004")
    second = clean_candidate("9000000000000000005")
    second["binary_original_sha256"] = first["binary_original_sha256"][:]
    with pytest.raises(HoldoutLeakageError, match="reused"):
        make_lock([first, second])


def test_no_sources_cannot_create_fictitious_gold_or_metrics():
    with pytest.raises(ValueError, match="No new"):
        make_lock([])
    lock = make_lock()
    with pytest.raises(ValueError, match="benchmark_pipeline"):
        semantic_metrics_or_not_measured(
            holdout_lock=lock,
            human_gold_freeze_receipt={"fake": True},
            sut_run_receipt={"fake": True},
        )
