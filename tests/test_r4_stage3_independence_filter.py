"""Source SHA-only exclusion; no legal text, no SUT, no human labels."""
from __future__ import annotations

import copy
import hashlib

import pytest

from src.modules.tender_operator_agent_demo.r4_stage3_independence_filter import (
    filter_attested_candidates_by_independence,
)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fixture():
    source = {
        "source_intent_sha256": h("preregistered"),
        "selected_discovery_only": [
            {"registry_number": f"9000000000000000{i:03d}", "source_rank":1 if i<=3 else 2,
             "source_card_rank":i}
            for i in range(1,9)
        ],
    }
    cases = [{
        "registry_number": row["registry_number"],
        "status": "ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED",
        "official_zip_sha256": h("zip" + str(i)),
        "official_xml_sha256": h("xml" + str(i)),
        "documents": [{"relative_path":f"original{i}.pdf","sha256":h("binary" + str(i))}],
    } for i,row in enumerate(source["selected_discovery_only"],1)]
    return source,cases


def audit(source,cases,**kwargs):
    return filter_attested_candidates_by_independence(
        immutable_discovery=source,
        official_cases=cases,
        previously_protected_numbers=kwargs.get("numbers",set()),
        previously_protected_original_sha256=kwargs.get("originals",set()),
        previously_protected_zip_sha256=kwargs.get("zips",set()),
        previously_protected_xml_sha256=kwargs.get("xmls",set()),
    )


def test_exact_ranked_eight_selected_when_all_unique():
    source,cases=fixture()
    report=audit(source,cases)
    assert len(report["accepted_source_only_cases"])==8
    assert report["excluded_cases_in_source_order"]==[]
    assert not report["sut_inference_permitted"]


def test_failed_official_xml_and_old_binary_and_cross_case_dup_are_not_backfilled():
    source,cases=fixture()
    cases[2]={"registry_number":cases[2]["registry_number"],"status":"INCOMPLETE_OFFICIAL_SOURCE"}
    cases[5]["documents"][0]["sha256"]=cases[0]["documents"][0]["sha256"]
    report=audit(source,cases,originals={cases[7]["documents"][0]["sha256"]})
    assert len(report["accepted_source_only_cases"])==5
    assert [v["reason"] for v in report["excluded_cases_in_source_order"]]==[
        "UNATTESTED_OFFICIAL_EIS_ORIGINALS",
        "REPEATED_ORIGINAL_BINARY_WITH_PREVIOUS_OR_EARLIER_CASE",
        "REPEATED_ORIGINAL_BINARY_WITH_PREVIOUS_OR_EARLIER_CASE",
    ]
    assert report["replacements_added"]==0
    assert report["human_gold"]==0


def test_prior_existing_notice_causes_hard_failure_without_any_cohort():
    source,cases=fixture()
    with pytest.raises(ValueError,match="already evaluated"):
        audit(source,cases,numbers={cases[0]["registry_number"]})


@pytest.mark.parametrize("change", [
    lambda source,cases:cases.pop(),
    lambda source,cases:cases.reverse(),
    lambda source,cases:cases[0].update(registry_number="9000000000000000999"),
])
def test_reordered_or_missing_fixed_source_candidate_fails(change):
    source,cases=fixture();change(source,cases)
    with pytest.raises(ValueError):
        audit(source,cases)


def test_known_reused_official_xml_rejected_even_with_unique_binaries():
    source,cases=fixture()
    cases[1]["official_xml_sha256"]=cases[0]["official_xml_sha256"]
    report=audit(source,cases)
    assert len(report["accepted_source_only_cases"])==7
    assert report["excluded_cases_in_source_order"][0]["reason"]=="REUSED_OFFICIAL_ZIP_OR_XML_WITH_PREVIOUS_OR_EARLIER_CASE"


def test_bad_file_sha_fail_closed():
    source,cases=fixture()
    cases[0]["documents"][0]["sha256"]="not-sha"
    with pytest.raises(ValueError,match="not SHA"):
        audit(source,cases)


def test_original_audit_is_read_only_and_repeatable():
    source,cases=fixture()
    original=copy.deepcopy(cases)
    a=audit(source,cases)
    b=audit(source,cases)
    assert a==b and cases==original



def test_generic_twelve_source_ranked_rows_fail_closed_without_backfill():
    source, rows = fixture()
    for index in range(9, 13):
        no = f"9000000000000000{index:03d}"
        source["selected_discovery_only"].append(
            {"registry_number": no, "source_rank": 3, "source_card_rank":index},
        )
        rows.append({
            "registry_number":no,"status":"ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED",
            "official_zip_sha256":h("zip"+str(index)),
            "official_xml_sha256":h("xml"+str(index)),
            "documents":[{"relative_path":f"original{index}.pdf","sha256":h("binary"+str(index))}],
        })
    protected=h("binary12")
    report=filter_attested_candidates_by_independence(
        immutable_discovery=source,official_cases=rows,
        previously_protected_numbers=set(),
        previously_protected_original_sha256={protected},
        previously_protected_zip_sha256=set(),
        previously_protected_xml_sha256=set(),
        expected_candidate_count=12,
    )
    assert report["source_candidate_count"]==12
    assert len(report["accepted_source_only_cases"])==11
    assert report["excluded_cases_in_source_order"][-1]["registry_number"]==rows[-1]["registry_number"]
    with pytest.raises(ValueError,match="preregistered"):
        filter_attested_candidates_by_independence(
            immutable_discovery=source,official_cases=rows,
            previously_protected_numbers=set(),
            previously_protected_original_sha256=set(),
            previously_protected_zip_sha256=set(),
            previously_protected_xml_sha256=set(),
            expected_candidate_count=8,
        )
