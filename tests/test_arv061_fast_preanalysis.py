from src.modules.tender_operator_agent_demo.decision_core import build_decision_core
from src.modules.tender_operator_agent_demo.fast_preanalysis import (
    fast_cited_preanalysis,
)


def test_grounded_facts_cited_and_no_autonomous_go():
    core = build_decision_core({"procurement_law": "44-ФЗ", "procurement_title": "Поставка оборудования", "application_deadline": "2026-10-20", "field_evidence": {"procurement_title": "eis_notice:subject", "application_deadline": "eis_notice:deadline"}})
    result = fast_cited_preanalysis(core, registry_number="0123456789026000001")
    assert result["subject"]["status"] == "KNOWN"
    assert result["subject"]["citations"][0]["source_ref"] == "eis_notice:subject"
    assert result["initial_price"]["status"] == "UNKNOWN"
    assert result["decision"] == "HUMAN_REVIEW_REQUIRED"
    assert result["external_action_allowed"] is False


def test_missing_evidence_fails_closed_even_if_value_is_present():
    result = fast_cited_preanalysis({"procurement_regime": "44fz", "facts": {"procurement_title": {"value": "Вымышленная закупка", "status": "KNOWN", "evidence": []}}})
    assert result["subject"] == {"status": "UNKNOWN", "value": None, "citations": []}


def test_unsupported_regime_is_unknown_and_bounded():
    result = fast_cited_preanalysis({"procurement_regime": "223fz", "readiness": [{"code": str(i), "summary": "x"} for i in range(40)]})
    assert result["status"] == "NEEDS_REVIEW"
    assert len(result["essential_requirements"]) == 12
    assert result["unknowns"][0]["code"] == "UNSUPPORTED_OR_UNVERIFIED_REGIME"


def test_existing_run_route_projects_without_reanalysis(monkeypatch):
    from types import SimpleNamespace

    from src.modules.tender_operator_agent_demo import router as api
    core = build_decision_core({"procurement_law": "44-ФЗ", "procurement_title": "Поставка", "field_evidence": {"procurement_title": "eis_notice:subject"}})
    monkeypatch.setattr(api, "get_uploaded_demo_report", lambda run_id: SimpleNamespace(decision_core=core))
    projected = api.get_tender_operator_fast_preanalysis("existing-run")
    assert projected["subject"]["value"] == "Поставка"
    assert projected["external_action_allowed"] is False


def test_public_exact_card_exposes_only_sourced_facts():
    from src.modules.tender_operator_agent_demo.fast_preanalysis import (
        preanalysis_from_public_search,
    )
    number = "0123456789026000001"
    def lookup(**kwargs):
        assert kwargs["query"] == number
        return {"outcome": "success_with_results", "cards": [{"reestr_number": number, "law": "44fz", "title": "Поставка оборудования", "deadline": "20.10.2026", "initial_price": 100000, "source_url": f"https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={number}"}]}
    result = preanalysis_from_public_search(f"https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={number}", search=lookup)
    assert result["subject"]["status"] == "KNOWN"
    assert result["application_deadline"]["citations"][0]["document"].startswith("Карточка")
    assert result["essential_requirements"]
    assert result["status"] == "NEEDS_REVIEW"
    assert result["latency_seconds"] >= 0


def test_public_mismatch_and_untrusted_url_fail_closed():
    import pytest

    from src.modules.tender_operator_agent_demo.fast_preanalysis import (
        parse_44fz_reference,
        preanalysis_from_public_search,
    )
    number = "0123456789026000001"
    for value in (f"https://evil.example/epz/order/notice/zk20/view/common-info.html?regNumber={number}", f"http://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={number}"):
        with pytest.raises(ValueError):
            parse_44fz_reference(value)
    result = preanalysis_from_public_search(number, search=lambda **kw: {"outcome": "success_with_results", "cards": [{"reestr_number": "9999999999999999999", "law": "44fz", "title": "Подмена"}]})
    assert result["subject"]["status"] == "UNKNOWN"
    assert result["external_action_allowed"] is False
