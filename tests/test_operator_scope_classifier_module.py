"""Scope extraction keeps existing evidence-locator facade and ambiguity."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_scope_classifier import (
    _SCOPE_SIGNALS,
    _classify_procurement_scope,
    _is_generic_procurement_scope_boilerplate,
    _scope_signal_evidence,
)


def test_legacy_scope_facades_remain_identical():
    assert legacy._SCOPE_SIGNALS is _SCOPE_SIGNALS
    assert legacy._classify_procurement_scope is _classify_procurement_scope
    assert legacy._scope_signal_evidence is _scope_signal_evidence
    assert legacy._is_generic_procurement_scope_boilerplate is _is_generic_procurement_scope_boilerplate


def test_services_subject_does_not_invent_goods():
    result = _classify_procurement_scope({"tender_title": "Оказание услуг содействия", "procurement": {}}, [], "")
    assert result["contains_goods"] is False
    assert result["classification_evidence"]


def test_missing_source_remains_unresolved():
    result = _classify_procurement_scope({"procurement": {}}, [], "")
    assert result["procurement_primary_scope"] == "unresolved"
    assert result["classification_evidence"] == []
    assert result["scope_classification_conflict"] is True
