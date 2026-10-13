"""Prove moved product projections preserve legacy callable routing."""

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_document_rows import (
    extract_meaningful_snippets,
)


@pytest.mark.parametrize(
    ("facade", "delegate", "arguments"),
    [
        ("_supply_item_to_row", "supply_item_to_row", (object(),)),
        ("_service_item_analysis_rows", "service_item_analysis_rows", ([],)),
        ("_extract_legacy_goods_spec_rows", "extract_legacy_goods_spec_rows", ("",)),
        (
            "_extract_meaningful_snippets",
            "extract_meaningful_snippets",
            ("text", ("text",)),
        ),
        ("_build_software_work_rows", "build_software_work_rows", ([],)),
    ],
)
def test_legacy_facade_delegates(monkeypatch, facade, delegate, arguments):
    sentinel = object()
    observed = []

    def fake(*args, **kwargs):
        observed.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(legacy, delegate, fake)
    assert getattr(legacy, facade)(*arguments) is sentinel
    assert len(observed) == 1
    assert observed[0][0] == arguments


def test_snippets_empty_source_and_missing_keyword():
    assert extract_meaningful_snippets("", ("условия",)) == []
    assert extract_meaningful_snippets("Документ без совпадений", ("цены",)) == []


def test_legacy_spec_empty_text_remains_empty():
    assert legacy._extract_legacy_goods_spec_rows("") == []
