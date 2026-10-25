"""Explicit official-source price-information request safety regression tests."""
from __future__ import annotations

from copy import deepcopy

from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
    projected_historical_eis_report,
    verified_noncompetitive_price_request,
)

NUMBER = "0348100024426000052"
REPORT = {
    "recommendation": "participate_conditionally",
    "recommendation_label": "Условно участвовать",
    "manual_checks": [],
    "executive_summary": [],
    "report_markdown": "# Historic",
    "decision_core": {"unknowns": []},
}


def official_metadata():
    return {
        "procurement_id": NUMBER,
        "notice_number": NUMBER,
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "notice_revision_requires_review": True,
        "procedure_type_evidence": {
            "authority": "eis_official",
            "procedure_type": "price_information_request",
            "procurement_id": NUMBER,
            "source_document_sha256": "c" * 64,
            "official_source_url": "https://zakupki.gov.ru/epz/sample",
        },
    }


def test_explicit_official_attestation_blocks_historical_go_and_preserves_original():
    m = official_metadata()
    before = deepcopy(REPORT)
    result = projected_historical_eis_report(m, REPORT)
    assert verified_noncompetitive_price_request(m)
    assert REPORT == before
    assert result["recommendation"] == "manual_review_required"
    assert "запрос ценовой информации" in result["recommendation_label"].lower()
    assert result["decision_core"]["noncompetitive_price_request"] is True
    assert result["decision_core"]["current_eis_revision_status"] == "UNKNOWN"
    assert result["manual_checks"][0].startswith("АРХИВНОЕ") or "ЦЕНОВОЙ" in result["manual_checks"][0]


def test_no_data_and_registry_number_do_not_establish_procedure_type():
    m = {"procurement_id": NUMBER, "procurement_source": "other",
         "get_docs_ip_status": "no_data"}
    assert not verified_noncompetitive_price_request(m)
    assert projected_historical_eis_report(m, REPORT) is REPORT


def test_secondary_source_must_not_claim_official_attestation():
    m = official_metadata()
    m["procedure_type_evidence"]["authority"] = "secondary_aggregator"
    assert not verified_noncompetitive_price_request(m)
    out = projected_historical_eis_report(m, REPORT)
    assert out["recommendation"] == "manual_review_required"
    assert "noncompetitive_price_request" not in out["decision_core"]


def test_wrong_procurement_identity_or_bad_sha_rejected():
    m = official_metadata()
    m["procedure_type_evidence"]["procurement_id"] = "0127100008626000013"
    assert not verified_noncompetitive_price_request(m)
    m["procedure_type_evidence"]["procurement_id"] = NUMBER
    m["procedure_type_evidence"]["source_document_sha256"] = "not_a_hash"
    assert not verified_noncompetitive_price_request(m)


def test_nonofficial_url_and_missing_procedure_type_rejected():
    m = official_metadata()
    m["procedure_type_evidence"]["official_source_url"] = "https://example.com/eis"
    assert not verified_noncompetitive_price_request(m)
    m["procedure_type_evidence"]["official_source_url"] = "https://zakupki.gov.ru/epz/sample"
    m["procedure_type_evidence"]["procedure_type"] = None
    assert not verified_noncompetitive_price_request(m)


def test_independent_official_noncompetitive_guard_without_archive_flag():
    m = official_metadata()
    m["procurement_source"] = "official_manual_eis_record"
    result = projected_historical_eis_report(m, REPORT)
    assert result["recommendation"] == "manual_review_required"
    assert result["decision_core"]["noncompetitive_price_request"] is True
    assert "current_eis_revision_status" not in result["decision_core"]


def test_idempotence_price_request_projection():
    m = official_metadata()
    out = projected_historical_eis_report(m, REPORT)
    out2 = projected_historical_eis_report(m, out)
    assert out2["manual_checks"] == out["manual_checks"]
    assert out2["executive_summary"] == out["executive_summary"]
    assert out2["report_markdown"] == out["report_markdown"]


def test_price_only_html_banner_and_idempotence():
    from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
        review_annotated_html,
    )
    m = official_metadata()
    m["procurement_source"] = "official_manual_eis_record"
    html = "<html><body><article>Historical GO</article></body></html>"
    result = review_annotated_html(m, html)
    assert 'data-arvectum-price-request-review="required"' in result
    assert "ЦЕНОВОЙ ИНФОРМАЦИИ" in result
    assert review_annotated_html(m, result) == result


def test_price_only_run_summary_fail_closed():
    from pydantic import BaseModel

    from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
        projected_historical_eis_run,
    )

    class Response(BaseModel):
        limitations: list[str] = []
        warnings: list[str] = []
        final_recommendation: str | None = "participate_conditionally"
        human_in_the_loop: bool = False
        external_actions: bool = True

    m = official_metadata()
    m["procurement_source"] = "official_manual_eis_record"
    original = Response()
    result = projected_historical_eis_run(m, original)
    assert original.final_recommendation == "participate_conditionally"
    assert result.final_recommendation is None
    assert result.external_actions is False
    assert result.human_in_the_loop is True
    assert "ЦЕНОВОЙ ИНФОРМАЦИИ" in result.limitations[0]
    assert projected_historical_eis_run(m, result).limitations == result.limitations


def test_price_only_binary_export_refused():
    import pytest
    from fastapi import HTTPException

    from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
        reject_unsafe_historical_eis_binary_export,
    )
    m = official_metadata()
    m["procurement_source"] = "official_manual_eis_record"
    with pytest.raises(HTTPException) as e:
        reject_unsafe_historical_eis_binary_export(m)
    assert e.value.status_code == 409
    assert "ЦЕНОВОЙ ИНФОРМАЦИИ" in e.value.detail


def test_unverified_aggregator_type_does_not_restrict_non_eis_report():
    from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
        reject_unsafe_historical_eis_binary_export,
        review_annotated_html,
    )
    m = official_metadata()
    m["procedure_type_evidence"]["authority"] = "secondary_aggregator"
    m["procurement_source"] = "other"
    reject_unsafe_historical_eis_binary_export(m)
    assert review_annotated_html(m, "<body>hi</body>") == "<body>hi</body>"
