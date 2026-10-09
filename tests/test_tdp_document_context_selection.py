"""Long document excerpt selection preserves exact normalized source ranges."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.document_context_selection import (
    select_document_context,
)


def test_short_document_unchanged_for_contract_compatibility():
    source = "Срок исполнения 10 дней"
    result = select_document_context(source, role="technical_spec")
    assert result.text == source
    assert result.truncated is False
    assert len(result.excerpts) == 1
    assert result.excerpts[0].ref == f"normalized:technical_spec:0-{len(source)}"


def test_late_contract_penalty_is_not_silently_dropped():
    source = ("Вводная информация. " * 2400) + ("Штраф и неустойка за просрочку. " * 10)
    result = select_document_context(source, role="contract_draft", max_chars=6000, window_chars=900)
    assert result.truncated
    assert len(result.text) <= 6000
    assert "неустойка" in result.text.lower()
    assert "НЕ ЯВЛЯЕТСЯ ПРОВЕРЕННОЙ ЦИТАТОЙ" in result.text
    assert len(result.excerpts) > 2
    assert any(x.char_end == len(source) for x in result.excerpts)
    for excerpt in result.excerpts:
        assert source[excerpt.char_start:excerpt.char_end] == excerpt.text
    assert list(result.excerpts) == sorted(result.excerpts, key=lambda x: x.char_start)


def test_mid_document_high_value_source_survives_budget():
    source = ("формальный текст " * 600) + "Требуется передача исходников сайта и техническая документация." + ("формальный текст " * 600)
    result = select_document_context(source, role="technical_spec", max_chars=6000, window_chars=900)
    assert result.truncated
    assert "передача исходников" in result.text


def test_wrong_source_does_not_get_fake_page_number_or_identification():
    source = "без сведений " * 2000
    result = select_document_context(source, role="notice", max_chars=6000, window_chars=900)
    assert result.truncated
    assert "PDF page" not in result.text
    assert "eis-xml:" not in result.text
    assert all(x.ref.startswith("normalized:notice:") for x in result.excerpts)


@pytest.mark.parametrize("budget,window", [(300, 100), (2000, 100), (1000, 1000)])
def test_invalid_window_contract_fails_closed(budget, window):
    with pytest.raises(ValueError):
        select_document_context("hello", role="notice", max_chars=budget, window_chars=window)


def test_real_controlled_workflow_uses_bounded_distributed_source(monkeypatch, tmp_path):
    """Proves the actual LLM adapter consumes selected excerpts, not first 6K."""
    from types import SimpleNamespace

    from src.modules.controlled_llm_prebid import service as controlled
    from src.modules.tender_operator_agent_demo.operator_llm_workflow import (
        run_controlled_operator_llm,
    )
    from src.shared.config.settings import Settings

    observed = {}

    def controlled_stub(_session, *, context, **_kwargs):
        observed.update(context["documents"])
        return SimpleNamespace(
            analysis_mode="test-bounded-source",
            resolved_provider="test",
            sections={},
            trace_ids=[],
            requirements={},
            supplier_questions=[],
            rfq_draft={},
            contract_risks=[],
            bid_decision=None,
        )

    monkeypatch.setattr(controlled, "run_controlled_tender_operator_workflow", controlled_stub)
    settings = Settings(database_url="sqlite:///" + str(tmp_path / "tdp-model-context.db"))
    long_contract = ("Текст договора. " * 5000) + "Штраф за просрочку исполнения составляет 0,1%."
    result = run_controlled_operator_llm(
        run_id="SYNTHETIC-BOUNDED-CONTEXT",
        notice_text="Разработка сайта музея.",
        technical_spec_text="Передать исходный код заказчику.",
        contract_draft_text=long_contract,
        quote_paths=[],
        settings_getter=lambda: settings,
    )
    assert result and result["analysis_mode"] == "test-bounded-source"
    assert observed["notice_text"] == "Разработка сайта музея."
    assert observed["technical_spec_text"] == "Передать исходный код заказчику."
    assert "Штраф за просрочку" in observed["contract_draft_text"]
    assert "normalized:contract_draft:" in observed["contract_draft_text"]
    assert len(observed["contract_draft_text"]) <= 11500
    assert len(observed["contract_draft_text"]) < len(long_contract) // 3
