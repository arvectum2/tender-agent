"""RI223 XML observations are separate from chunks, LLM and legal conclusions."""

from __future__ import annotations

from copy import deepcopy

from src.tender_research.api import _to_analyze_response
from src.tender_research.rag.analysis_service import _build_report_markdown
from src.tender_research.rag.ri223_source_facts import (
    project_ri223_source_facts,
    render_ri223_source_facts,
)
from src.tender_research.rag.schemas import TenderAnalysisResult


def _evidence(xml: str, xpath: str = "/purchaseNotice/body/item/purchaseNoticeData"):
    return {
        "regime": "223fz",
        "source": "RI223_getDocsIP",
        "archive_sha256": "a" * 64,
        "xml_member": xml,
        "xml_sha256": "b" * 64,
        "xpath": xpath,
    }


def _payload():
    return {
        "source_regime": "223fz",
        "source_subsystem": "RI223",
        "archive_sha256": "a" * 64,
        "notice_version": "3",
        "notice_effective_status": "UNKNOWN",
        "procurement_status": "UNKNOWN",
        "notice_versions": [
            {
                "source_version": ver,
                "publication_datetime": pub,
                "submission_close_datetime": date,
                "evidence": _evidence(f"v{ver}.xml"),
            }
            for ver, pub, date in [
                ("1", "2026-09-15", "2026-10-01T16:00:00"),
                ("2", "2026-10-01", "2026-10-12T16:00:00"),
                ("3", "2026-10-08", "2026-10-20T16:00:00"),
            ]
        ],
        "lots": [
            {
                "ordinal_number": "1",
                "subject": "Деревянные опоры",
                "initial_sum": "100000",
                "currency_code": "RUB",
                "positions": [
                    {
                        "ordinal_number": "1",
                        "quantity": "3",
                        "okpd2_code": "16.10",
                        "evidence": _evidence(
                            "v3.xml", "/purchaseNotice/lots/lot[1]/lotItem[1]"
                        ),
                    }
                ],
                "evidence": _evidence("v3.xml", "/purchaseNotice/lots/lot[1]"),
            },
            {
                "ordinal_number": "2",
                "subject": "Кабель",
                "initial_sum": "200000",
                "currency_code": "RUB",
                "positions": [
                    {
                        "ordinal_number": "1",
                        "quantity": "7",
                        "okpd2_code": "27.32",
                        "evidence": _evidence(
                            "v3.xml", "/purchaseNotice/lots/lot[2]/lotItem[1]"
                        ),
                    }
                ],
                "evidence": _evidence("v3.xml", "/purchaseNotice/lots/lot[2]"),
            },
        ],
        "explanations": [
            {
                "source_guid": "original-question",
                "request_subject_info": "Как трактовать требования к опорам?",
                "request_date": "2026-09-21",
                "publish_date": "2026-09-23",
                "source_status_code": "P",
                "source_lot_binding": "UNKNOWN",
                "evidence": _evidence(
                    "explanation.xml", "/explanation/body/item/explanationData"
                ),
            }
        ],
    }


def test_ri223_source_facts_have_individual_xml_hash_xpath_and_no_legal_inference():
    facts = project_ri223_source_facts("223fz", _payload())
    assert [f["kind"] for f in facts] == [
        "notice_revision",
        "notice_revision",
        "notice_revision",
        "lot",
        "lot_position",
        "lot",
        "lot_position",
        "explanation",
    ]
    assert [x["fields"]["submission_close_datetime"] for x in facts[:3]] == [
        "2026-10-01T16:00:00",
        "2026-10-12T16:00:00",
        "2026-10-20T16:00:00",
    ]
    assert [x["fields"]["initial_sum"] for x in facts if x["kind"] == "lot"] == [
        "100000",
        "200000",
    ]
    assert [
        x["fields"]["lot_ordinal_number"] for x in facts if x["kind"] == "lot_position"
    ] == ["1", "2"]
    assert facts[-1]["fields"]["source_lot_binding"] == "UNKNOWN"
    assert all(f["interpretation"] == "XML_SOURCE_OBSERVATION_ONLY" for f in facts)
    assert all(f["evidence"]["xml_sha256"] == "b" * 64 for f in facts)


def test_source_facts_must_be_verified_ri223_and_parent_hash_match():
    payload = _payload()
    assert project_ri223_source_facts("44fz", payload) == []
    assert project_ri223_source_facts(None, payload) == []
    assert project_ri223_source_facts("223fz", {}) == []
    missing = deepcopy(payload)
    missing["source_subsystem"] = "PRIZ"
    assert project_ri223_source_facts("223fz", missing) == []
    mutated = deepcopy(payload)
    mutated["archive_sha256"] = "z" * 64
    assert project_ri223_source_facts("223fz", mutated) == []
    forgery = deepcopy(payload)
    forgery["lots"][0]["evidence"]["archive_sha256"] = "c" * 64
    filtered = project_ri223_source_facts("223fz", forgery)
    assert len(filtered) == 7
    assert all(x["fields"].get("subject") != "Деревянные опоры" for x in filtered)
    invalid = deepcopy(payload)
    invalid["explanations"][0]["evidence"]["xml_sha256"] = "not_sha"
    assert [x["kind"] for x in project_ri223_source_facts("223fz", invalid)].count(
        "explanation"
    ) == 0


def test_nested_source_payload_and_missing_observations_fail_safe():
    payload = _payload()
    assert len(project_ri223_source_facts("223fz", {"soap_raw_payload": payload})) == 8
    tampered = deepcopy(payload)
    tampered["lots"] = ["garbage"] * 300
    tampered["explanations"] = [None] * 300
    assert [x["kind"] for x in project_ri223_source_facts("223fz", tampered)] == [
        "notice_revision",
        "notice_revision",
        "notice_revision",
    ]


def test_report_and_api_expose_source_facts_separately_from_document_citations():
    facts = project_ri223_source_facts("223fz", _payload())
    markdown = _build_report_markdown(
        "32616376947",
        [],
        False,
        None,
        "data_platform",
        "hybrid",
        ri223_source_observations=facts,
    )
    assert "Структурированные наблюдения ЕИС (223-ФЗ)" in markdown
    assert "2026-10-20T16:00:00" in markdown
    assert "explanation.xml" in markdown
    assert "XPath" in markdown and "SHA-256" in markdown
    assert "правовая экспертиза" in markdown
    assert "Совокупная цена многолотовой закупки" in markdown
    assert not render_ri223_source_facts([])

    result = TenderAnalysisResult(
        status="completed_with_warnings",
        registry_number="32616376947",
        sections=[],
        sections_count=0,
        sources_count=0,
        report_markdown=markdown,
        ri223_source_observations=facts,
    )
    response = _to_analyze_response(result)
    assert len(response.ri223_source_observations) == 8
    assert response.sources_count == 0  # XML evidence != RAG chunk citations
    assert response.ri223_source_observations[-1]["kind"] == "explanation"


def test_ri223_review_flags_are_source_bound_and_non_decisional():
    from src.tender_research.rag.ri223_source_facts import (
        derive_ri223_review_flags,
        render_ri223_review_flags,
    )

    facts = project_ri223_source_facts("223fz", _payload())
    flags = derive_ri223_review_flags(facts)
    assert [f["code"] for f in flags] == [
        "OBSERVED_SUBMISSION_DEADLINE_CHANGE",
        "EXPLANATIONS_REQUIRE_DOCUMENT_REVIEW",
        "MULTI_LOT_REQUIRES_SEPARATE_REVIEW",
    ]
    assert all(flag["status"] == "NEEDS_REVIEW" for flag in flags)
    assert all(flag["legal_effect"] == "UNKNOWN" for flag in flags)
    assert flags[0]["observed_deadlines"] == [
        {"source_version": "1", "submission_close_datetime": "2026-10-01T16:00:00"},
        {"source_version": "2", "submission_close_datetime": "2026-10-12T16:00:00"},
        {"source_version": "3", "submission_close_datetime": "2026-10-20T16:00:00"},
    ]
    assert flags[1]["observed_explanation_count"] == 1
    assert flags[2]["observed_lot_count"] == 2
    assert all(e["xml_sha256"] == "b" * 64 for f in flags for e in f["evidence"])
    assert "юридическую силу" in "\n".join(render_ri223_review_flags(flags))
    assert render_ri223_review_flags([]) == []
    report = _build_report_markdown(
        "32616376947",
        [],
        False,
        None,
        "data_platform",
        "hybrid",
        ri223_source_observations=facts,
        ri223_review_flags=flags,
    )
    assert "NEEDS_REVIEW" in report
    assert "2026-10-20T16:00:00" in report
    assert "юридическую силу" in report


def test_ri223_review_flags_do_not_activate_without_real_changes():
    from src.tender_research.rag.ri223_source_facts import derive_ri223_review_flags

    facts = project_ri223_source_facts("223fz", _payload())
    # A single observed notice, one lot, no explanation does not justify a flag.
    isolated = [row for row in facts if row["kind"] == "notice_revision"][:1]
    isolated += [row for row in facts if row["kind"] in {"lot", "lot_position"}][:2]
    assert derive_ri223_review_flags(isolated) == []
    assert (
        derive_ri223_review_flags(project_ri223_source_facts("44fz", _payload())) == []
    )
    assert derive_ri223_review_flags([]) == []


def test_ri223_review_flags_are_exposed_via_existing_api():
    from src.tender_research.rag.ri223_source_facts import derive_ri223_review_flags

    facts = project_ri223_source_facts("223fz", _payload())
    flags = derive_ri223_review_flags(facts)
    result = TenderAnalysisResult(
        status="completed_with_warnings",
        registry_number="32616376947",
        sections=[],
        sections_count=0,
        sources_count=0,
        ri223_source_observations=facts,
        ri223_review_flags=flags,
    )
    response = _to_analyze_response(result)
    assert len(response.ri223_review_flags) == 3
    assert response.sources_count == 0
    assert (
        response.ri223_review_flags[-1]["code"] == "MULTI_LOT_REQUIRES_SEPARATE_REVIEW"
    )
