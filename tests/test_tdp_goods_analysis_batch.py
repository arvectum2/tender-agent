"""Legacy goods source reconciliation and preliminary-analysis compatibility."""

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


@pytest.mark.parametrize(
    ("facade", "delegate", "args", "kwargs"),
    [
        ("_merge_supply_items", "project_merge_supply_items", ([],), {}),
        (
            "_collect_unmerged_source_items",
            "project_collect_unmerged_source_items",
            ([],),
            {},
        ),
        (
            "_build_goods_preliminary_analysis",
            "project_build_goods_preliminary_analysis",
            (),
            {
                "metadata": {},
                "documents": [],
                "technical_spec_text": "",
                "contract_draft_text": "",
                "notice_text": "",
            },
        ),
    ],
)
def test_facade_forwards_existing_contract(monkeypatch, facade, delegate, args, kwargs):
    sentinel = object()
    calls = []

    def fake(*values, **named):
        calls.append((values, named))
        return sentinel

    monkeypatch.setattr(legacy, delegate, fake)
    assert getattr(legacy, facade)(*args, **kwargs) is sentinel
    assert len(calls) == 1
    assert calls[0][0] == args
    for key, value in kwargs.items():
        assert calls[0][1][key] == value


def test_empty_source_reconciliation_remains_empty():
    assert legacy._merge_supply_items([]) == []
    assert legacy._collect_unmerged_source_items([]) == []


def test_empty_preliminary_analysis_preserves_required_keys():
    payload = legacy._build_goods_preliminary_analysis(
        metadata={},
        documents=[],
        technical_spec_text="",
        contract_draft_text="",
        notice_text="",
    )
    assert payload["procurement_kind"] == "goods"
    assert payload["supply_items"] == []
    assert isinstance(payload["next_actions"], list)


def test_merging_same_goods_preserves_evidence_sources():
    def item(origin: str):
        return legacy.SupplyItem(
            item_no="1",
            name="Офисная бумага",
            quantity="10",
            unit="уп.",
            characteristics=["Формат А4"],
            gost=[],
            equivalent_allowed=None,
            source_document=origin,
            source_kind="technical_specification",
            confidence="high",
            raw_fragment="Бумага А4 10 уп.",
        )

    result = legacy._merge_supply_items(
        [item("notice.xml"), item("specification.docx")]
    )
    assert len(result) == 1
    assert result[0].source_document == "notice.xml"
    assert "specification.docx" in result[0].source_documents


def test_source_fact_constructor_is_injected_and_retains_provenance(monkeypatch):
    from types import SimpleNamespace

    source = SimpleNamespace(
        text="",
        display_name="Описание объекта закупки",
        role="technical_spec",
        extension=".docx",
    )
    fact = SimpleNamespace(
        fact_type="PRODUCT_ITEM",
        value="Бумага для офисной печати А4",
        source_document="object-spec.docx",
        confidence="high",
        excerpt="Бумага для офисной печати А4",
        source_row_number=7,
        fact_id="fact-7",
        extraction_strategy="source_fact_extractor",
    )
    monkeypatch.setattr(legacy, "extract_goods_source_facts", lambda documents: [fact])
    items = legacy._collect_unmerged_source_items([source])
    assert len(items) == 1
    assert items[0].source_document == "object-spec.docx"
    assert items[0].source_documents == ["object-spec.docx"]
    assert items[0].evidence_id == "fact-7"
    assert items[0].quantity_status == "not_specified"
