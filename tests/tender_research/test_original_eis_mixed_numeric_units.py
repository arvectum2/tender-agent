"""Contract unit forms and original XML source-field money remain strictly checked."""
from dataclasses import replace

from src.tender_research.rag.numeric_absence_guard import contradicted_absence
from src.tender_research.rag.numeric_claim_evidence import (
    _observed_values,
    unsupported_explicit_numeric_claim,
)
from src.tender_research.rag.search_types import RagSearchHit


def _hit(text: str) -> RagSearchHit:
    return RagSearchHit(
        chunk_id="source-1",score=1.0,
        registry_number="0163200000326005243",tender_id="tid",
        tender_title="Дума",customer_name="Дума",document_id="doc-1",
        file_name="Original source",chunk_index=0,preview=text[:120],text=text,
    )


XML = (
    "Источник: официальный getDocsIP; Номер извещения 0163200000326005243. "
    "НМЦК РУБ — сумма контракта, НЕ лимит квалификационного опыта: 497178.33 "
    "Окончание заявок: 2026-10-30T11:00:00+03:00"
)


def test_labelled_official_nmc_rub_is_source_value_not_new_value():
    assert ("rub", "497178.33") in _observed_values(XML)
    assert unsupported_explicit_numeric_claim(
        "НМЦК составляет 497 178,33 руб.", [_hit(XML)],
    ) is None


def test_labelled_nmc_never_licenses_other_money_amounts():
    assert unsupported_explicit_numeric_claim(
        "НМЦК равна 15 000 000 руб.", [_hit(XML)]
    ) == "rub"


def test_contract_written_percent_and_sign_share_explicit_value():
    text = "Штраф составляет 1 процента цены, до 10 процентов; обеспечение 0,5%."
    observed = _observed_values(text)
    assert {("percent","1"),("percent","10"),("percent","0.5")} <= observed
    assert unsupported_explicit_numeric_claim(
        "Штраф 1%, другая санкция 10%, обеспечение 0.5%.", [_hit(text)]
    ) is None


def test_contract_source_cannot_authorize_another_percentage():
    text = "Штраф 1 процента, ограничение 10 процентов."
    assert unsupported_explicit_numeric_claim(
        "Штраф равен 25%.", [_hit(text)]
    ) == "percent"


def test_false_nmc_absence_rejected_for_attested_original_field():
    answer = "Начальная (максимальная) цена контракта не подтверждена выбранными фрагментами."
    assert contradicted_absence(answer, [_hit(XML)]) == "price"
    assert contradicted_absence("НМЦК не указана.", [_hit(XML)]) == "price"


def test_experience_threshold_not_evidence_of_nmc():
    answer = "Начальная (максимальная) цена контракта не подтверждена выбранными фрагментами."
    assert contradicted_absence(
        answer, [_hit("Квалификационный опыт от 15 000 000 рублей.")]
    ) is None


def test_source_provenanced_price_must_be_present_in_provided_chunks():
    doc = _hit(XML)
    other = replace(doc,text="Только перечень аналогичных договоров, без НМЦК.")
    assert contradicted_absence("НМЦК не подтверждена.", [other]) is None



def test_llm_limited_retry_can_recover_false_nmc_absence(monkeypatch):
    from unittest.mock import Mock

    from src.tender_research.rag.llm import LocalChatLlmClient, RagAnswer

    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8081/v1",model_name="Gemma",
        max_context_chars=10000,
    )
    generated = iter([
        RagAnswer(
            answer="",sources=[],used_chunks_count=1,model="Gemma",
            error="Local LLM answer incorrectly claims missing numeric evidence for price;"
                  " review original cited source chunks.",
        ),
        RagAnswer(answer="НМЦК составляет 497 178,33 руб. Источник source-1.",
                  sources=[],used_chunks_count=1,model="Gemma"),
    ])
    fake = Mock(side_effect=lambda *args,**kwargs: next(generated))
    monkeypatch.setattr(client,"_generate_with_retry",fake)
    answer=client.generate_answer("Назови НМЦК",[_hit(XML)],analysis_mode="detailed")
    assert answer.attempt_count==2
    assert fake.call_count==2
    assert "497178.33 руб." in fake.call_args.args[0]
