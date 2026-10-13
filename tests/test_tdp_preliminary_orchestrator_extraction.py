"""Preliminary procurement orchestrator extraction contract and runtime helper binding."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def test_preliminary_orchestrator_old_facade_delegates(monkeypatch):
    calls = []
    expected = {"overview": {"test_marker": "delegated"}}

    def fake(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(legacy, "project_build_preliminary_procurement_analysis", fake)
    kwargs = {
        "metadata": {},
        "documents": [],
        "technical_spec_text": "",
        "contract_draft_text": "",
        "notice_text": "",
    }
    result = legacy._build_preliminary_procurement_analysis(**kwargs)
    assert isinstance(result, dict)
    assert len(calls) == 1
    assert all(calls[0][name] == value for name, value in kwargs.items())
    assert callable(calls[0]["_build_goods_preliminary_analysis"])
    assert callable(calls[0]["_build_services_preliminary_analysis"])


def test_preliminary_orchestrator_preserves_real_empty_goods_payload():
    payload = legacy._build_preliminary_procurement_analysis(
        metadata={"procurement_kind": "goods"},
        documents=[],
        technical_spec_text="",
        contract_draft_text="",
        notice_text="",
    )
    assert isinstance(payload, dict)
    assert "overview" in payload


def test_preliminary_orchestrator_preserves_empty_service_payload():
    payload = legacy._build_preliminary_procurement_analysis(
        metadata={"procurement_kind": "services"},
        documents=[],
        technical_spec_text="",
        contract_draft_text="",
        notice_text="",
    )
    assert isinstance(payload, dict)
    assert "overview" in payload
