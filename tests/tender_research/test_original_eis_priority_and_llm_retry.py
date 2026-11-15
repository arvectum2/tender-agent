"""Source scope, identity, physical SHA and bounded model provenance retry tests."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.tender_research.rag import official_eis_priority as priority
from src.tender_research.rag.llm import LocalChatLlmClient, RagAnswer
from src.tender_research.rag.search_types import RagSearchHit

NUMBER = "0163200000326005243"
ARCHIVE = "4cec297f6bd040723105fab5ac03a3d10e986b3c03b03032a7da3c3769389d5d"


def hit(cid: str, registry: str = NUMBER, tender: str = "tid") -> RagSearchHit:
    return RagSearchHit(
        chunk_id=cid, score=.22, registry_number=registry, tender_id=tender,
        tender_title="Официальная закупка", customer_name="Дума",
        document_id="doc", file_name="Оригинал ЕИС",
        chunk_index=0, preview="Контекст", text="НМЦК 497178.33; Цена 30%.",
    )


def repo_fixture(tmp_path: Path, monkeypatch, *, suffix: str):
    monkeypatch.setattr(priority, "_OWNER_ORIGINAL_ROOT", tmp_path)
    parent = tmp_path / NUMBER / ARCHIVE
    parent.mkdir(parents=True)
    binary = b"verified fake binary for test only"
    path = parent / "document.docx"
    path.write_bytes(binary)
    path.chmod(0o600)
    schema, sha_field = priority._SIGNATURES[suffix]
    document = SimpleNamespace(
        id="verified_doc", tender_id="tid", local_path=str(path),
        sha256=sha256(binary).hexdigest(), source_document_id="eis-archived-v2"+suffix,
        raw_meta={"schema":schema,sha_field:ARCHIVE,"derived_docx_sha256":sha256(binary).hexdigest()},
    )
    tender = SimpleNamespace(id="tid",documents=[document])
    chunk = SimpleNamespace(id="exact_chunk",document_id="verified_doc",
                            tender_id="tid", chunk_index=0,
                            text="Оригинальное извещение НМЦК 497178.33 и окончание 30.10.2026 11:00")
    context = {
        "chunk_id":"exact_chunk","registry_number":NUMBER,"tender_id":"tid",
        "document_id":"verified_doc","tender_title":"Дума","customer_name":"Дума",
        "file_name":"Производный XML","chunk_index":0,"text":chunk.text,
    }
    repo=Mock()
    repo.get_tender_by_registry_number.return_value=tender
    repo.list_chunks_by_tender.return_value=[chunk]
    repo.get_chunk_context.return_value=context
    return repo,document,path,context


def test_source_xml_priority_exact_tender_scoped_no_foreign_hits(tmp_path,monkeypatch):
    repo,doc,_path,_context=repo_fixture(tmp_path,monkeypatch,suffix="-derived-full-xml")
    result=priority.prioritize_original_eis_hits(
        repo, [hit("old"),hit("foreign",registry="0000000000000000000"),
               hit("foreign_tender",tender="other")],
        registry_number=NUMBER,section_id="subject",max_chunks=5)
    assert [x.chunk_id for x in result] == ["exact_chunk","old"]
    assert result[0].score == 1.0
    assert result[0].document_id == doc.id


def test_original_criteria_priority_exact_provenance(tmp_path,monkeypatch):
    repo,_doc,_path,_context=repo_fixture(tmp_path,monkeypatch,suffix="-derived-criteria-percent")
    result=priority.prioritize_original_eis_hits(
        repo, [hit("old")],registry_number=NUMBER,
        section_id="evaluation_criteria",max_chunks=3)
    assert result[0].chunk_id == "exact_chunk"


@pytest.mark.parametrize("tamper",["wrong_archive","different_content","world_readable","wrong_registry_context","other_document"])
def test_foreign_or_modified_source_is_never_added(tmp_path,monkeypatch,tamper):
    repo,doc,path,ctx=repo_fixture(tmp_path,monkeypatch,suffix="-derived-full-xml")
    if tamper == "wrong_archive":
        doc.raw_meta["source_original_zip_sha256"]="0"*64
    if tamper == "different_content":
        path.write_bytes(b"tampered by attacker")
    if tamper == "world_readable":
        path.chmod(0o644)
    if tamper == "wrong_registry_context":
        ctx["registry_number"]="wrong"
    if tamper == "other_document":
        ctx["document_id"]="unrelated"
    result=priority.prioritize_original_eis_hits(
        repo,[hit("old")],registry_number=NUMBER,
        section_id="subject",max_chunks=5)
    assert [x.chunk_id for x in result]==["old"]


def test_other_procurement_does_not_read_sensitive_originals(tmp_path,monkeypatch):
    repo,_,_,_=repo_fixture(tmp_path,monkeypatch,suffix="-derived-full-xml")
    old=[hit("old","other")]
    assert priority.prioritize_original_eis_hits(
        repo,old,registry_number="some-other-tender",section_id="subject",
        max_chunks=5) is old
    repo.get_tender_by_registry_number.assert_not_called()


def test_llm_retries_once_with_same_context_and_no_failed_answer():
    client=LocalChatLlmClient(base_url="http://127.0.0.1:8081/v1",model_name="Gemma",max_context_chars=10000)
    seen=[]
    def fake(question,contexts,**kwargs):
        seen.append((question,[h.chunk_id for h in contexts]))
        if len(seen)==1:
            return RagAnswer(
                answer="", sources=[], used_chunks_count=1,model="Gemma",
                error="Local LLM answer includes an unsupported explicit numeric value with unit percent;"
                      " review original cited source chunks.")
        return RagAnswer(answer="Цена 30%, chunk_id=exact_chunk, registry_number="+NUMBER,
                         sources=[],used_chunks_count=1,model="Gemma")
    client._generate_with_retry=fake
    context=[hit("exact_chunk")]
    answer=client.generate_answer("Назови цену",context,registry_number=NUMBER,analysis_mode="detailed")
    assert answer.error is None
    assert answer.attempt_count==2
    assert len(seen)==2
    assert all(ids==["exact_chunk"] for _,ids in seen)
    assert "30%" in seen[1][0]
    assert "99%" not in seen[1][0]


def test_llm_does_not_retry_unrelated_error_or_fast_mode():
    client=LocalChatLlmClient(base_url="http://127.0.0.1:8081/v1",model_name="Gemma",max_context_chars=10000)
    fake=Mock(return_value=RagAnswer(
        answer="",sources=[],used_chunks_count=1,model="Gemma",
        error="Local LLM request timed out."))
    client._generate_with_retry=fake
    assert client.generate_answer("Анализ",[hit("exact_chunk")],analysis_mode="detailed").attempt_count==1
    assert fake.call_count==1
    fake.reset_mock()
    fake.return_value=RagAnswer(
        answer="",sources=[],used_chunks_count=1,model="Gemma",
        error="Local LLM answer cites unknown or modified source chunk identifiers.")
    assert client.generate_answer("Анализ",[hit("exact_chunk")],analysis_mode="fast").attempt_count==1
    assert fake.call_count==1


def test_second_rejected_answer_stays_rejected_and_bounded():
    client=LocalChatLlmClient(base_url="http://127.0.0.1:8081/v1",model_name="Gemma",max_context_chars=10000)
    fake=Mock(return_value=RagAnswer(
        answer="",sources=[],used_chunks_count=1,model="Gemma",
        error="Local LLM answer cites unknown or modified source chunk identifiers."))
    client._generate_with_retry=fake
    result=client.generate_answer("Документация",[hit("exact_chunk")],analysis_mode="detailed")
    assert fake.call_count==2
    assert result.answer==""
    assert result.error
    assert result.attempt_count==2


def test_invalid_derived_source_does_not_allow_cross_tender_fallback(tmp_path,monkeypatch):
    repo,_doc,path,_context=repo_fixture(tmp_path,monkeypatch,suffix="-derived-full-xml")
    path.write_bytes(b"altered")
    result=priority.prioritize_original_eis_hits(
        repo,[hit("own"),hit("cross",registry="other",tender="other")],
        registry_number=NUMBER,section_id="subject",max_chunks=5)
    assert [h.chunk_id for h in result]==["own"]


def test_customer_contract_sections_never_receive_foreign_retrieval_hits(tmp_path,monkeypatch):
    repo,_doc,_path,_context=repo_fixture(tmp_path,monkeypatch,suffix="-derived-full-xml")
    for section_id in ("customer_requirements","contract_terms"):
        result=priority.prioritize_original_eis_hits(
            repo,[hit("good"),hit("other",registry="foreign",tender="x")],
            registry_number=NUMBER,section_id=section_id,max_chunks=5)
        assert [x.chunk_id for x in result]==["good"]



def test_retry_explicit_currency_and_percent_values_are_context_scoped():
    doc=hit("original_xml_chunk")
    doc=__import__("dataclasses").replace(
        doc, text="НМЦК 497 178,33 руб. Цена критерия 30 %."
    )
    question=LocalChatLlmClient._evidence_repair_question(
        "Назови настоящую НМЦК", [doc],
        "Local LLM answer includes an unsupported explicit numeric value with unit rub",
    )
    assert "497178.33 руб." in question
    assert "30%" in question
    assert "original_xml_chunk" in question
    assert "15 000 000" not in question


def test_retry_absent_percent_and_rub_never_invents_values():
    doc=__import__("dataclasses").replace(
        hit("contract_chunk"), text="Срок исполнения договора до конца 2026 года."
    )
    question=LocalChatLlmClient._evidence_repair_question(
        "Договор", [doc],
        "Local LLM answer includes an unsupported explicit numeric value with unit percent",
    )
    assert "список явно присутствующих денежных значений: отсутствует" in question
    assert "список явно присутствующих процентных значений: отсутствует" in question
