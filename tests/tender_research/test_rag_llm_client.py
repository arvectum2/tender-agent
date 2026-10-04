from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from urllib.error import URLError

from src.tender_research.rag.llm import LocalChatLlmClient
from src.tender_research.rag.retriever import RagSearchHit


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _hits() -> list[RagSearchHit]:
    return [
        RagSearchHit(
            chunk_id="chunk-1",
            score=0.91,
            registry_number="123",
            tender_id="tender-1",
            tender_title="Тестовая закупка",
            customer_name="Тестовый заказчик",
            document_id="doc-1",
            file_name="spec.docx",
            chunk_index=0,
            preview="Требования к составу заявки...",
            text="Требования к составу заявки и инструкция по заполнению.",
        )
    ]


def test_local_chat_llm_client_success(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResponse(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "Краткий ответ:\nДа.\n\nПодробности:\nПо найденному фрагменту требования указаны.\n\nИсточники:\n1. spec.docx, chunk_id=chunk-1, registry_number=123"
                            }
                        }
                    ]
                },
                ensure_ascii=False,
            )
        ),
    )

    answer = client.generate_answer("Какие требования к составу заявки?", _hits(), registry_number="123")

    assert answer.error is None
    assert answer.model == "qwen-local"
    assert answer.used_chunks_count == 1
    assert "Краткий ответ" in answer.answer
    assert answer.sources[0].document_file_name == "spec.docx"


def test_local_chat_llm_client_server_unavailable(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("refused")),
    )

    answer = client.generate_answer("Вопрос", _hits())

    assert answer.error == "Local LLM server is unavailable: refused"
    assert answer.sources


def test_local_chat_llm_client_timeout(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError("slow")),
    )

    answer = client.generate_answer("Вопрос", _hits())

    assert answer.error == "Local LLM request timed out."


def test_local_chat_llm_client_non_json_response(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResponse("not-json"),
    )

    answer = client.generate_answer("Вопрос", _hits())

    assert answer.error == "Local LLM returned a non-JSON response."


def test_local_chat_llm_client_empty_response(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        lambda request, timeout: _FakeResponse(json.dumps({"choices": [{"message": {"content": ""}}]})),
    )

    answer = client.generate_answer("Вопрос", _hits())

    assert answer.error == "Local LLM returned an empty response."


def test_local_chat_llm_client_retries_with_fewer_contexts_on_context_limit(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
        max_context_chars=10000,
    )
    observed_inputs: list[int] = []
    hits = _hits() * 2

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["messages"][1]["content"]
        observed_inputs.append(prompt.count("[Источник "))
        if observed_inputs[-1] > 1:
            raise HTTPError(
                request.full_url,
                400,
                "bad request",
                hdrs=None,
                fp=io.BytesIO(
                    b'{"error":{"message":"request exceeds the available context size","type":"exceed_context_size_error"}}'
                ),
            )
        return _FakeResponse(
            json.dumps({"choices": [{"message": {"content": "Краткий ответ:\nОк.\n\nИсточники:\n1. spec.docx, chunk_id=chunk-1, registry_number=123"}}]})
        )

    monkeypatch.setattr("src.tender_research.rag.llm.urllib.request.urlopen", fake_urlopen)

    answer = client.generate_answer("Вопрос", hits)

    assert answer.error is None
    assert observed_inputs == [2, 1]
    assert answer.used_chunks_count == 1


def test_local_chat_llm_client_fast_mode_bounds_output_tokens(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8081/v1",
        model_name="arvectum-gemma4-12b-it-qat-q4_0",
    )
    observed: dict = {}

    def fake_urlopen(request, timeout):
        observed.update(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(
            json.dumps({"choices": [{"message": {"content": "Краткий ответ:\nОк."}}]})
        )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        fake_urlopen,
    )

    answer = client.generate_answer(
        "Вопрос",
        _hits(),
        registry_number="123",
        analysis_mode="fast",
    )

    assert answer.error is None
    assert observed["max_tokens"] == 384


def test_local_chat_llm_client_reports_prompt_metrics() -> None:
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1",
        model_name="qwen-local",
    )

    metrics = client.build_prompt_metrics(
        "Какие требования к составу заявки?",
        _hits(),
        registry_number="123",
        analysis_mode="fast",
    )

    assert metrics["context_chars"] > 0
    assert metrics["prompt_chars"] >= metrics["user_prompt_chars"]


def test_local_chat_llm_client_includes_source_bound_procurement_facts(monkeypatch):
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8081/v1",
        model_name="arvectum-gemma4-12b-it-qat-q4_0",
    )
    observed: dict = {}

    def fake_urlopen(request, timeout):
        observed.update(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(
            json.dumps({"choices": [{"message": {"content": "Краткий ответ:\nОк."}}]})
        )

    monkeypatch.setattr(
        "src.tender_research.rag.llm.urllib.request.urlopen",
        fake_urlopen,
    )

    answer = client.generate_answer(
        "Какая дата окончания подачи заявок?",
        _hits(),
        registry_number="123",
        analysis_mode="fast",
        source_facts=(
            "Номер закупки: 123\n"
            "Окончание подачи заявок: 05.10.2026 10:00 (МСК+2)\n"
            "Состав полученной документации: Извещение.docx; Проект контракта.docx"
        ),
    )

    assert answer.error is None
    prompt = observed["messages"][1]["content"]
    assert "Структурированные source-bound факты источников" in prompt
    assert "05.10.2026 10:00 (МСК+2)" in prompt
    assert "Извещение.docx; Проект контракта.docx" in prompt


def test_local_chat_llm_client_guardrails_keep_contract_obligations_separate():
    client = LocalChatLlmClient(
        base_url="http://127.0.0.1:8081/v1",
        model_name="arvectum-gemma4-12b-it-qat-q4_0",
    )
    system_prompt = client._system_prompt(analysis_mode="fast")
    assert "обеспечение исполнения контракта" in system_prompt
    assert "гарантия на результат услуг" in system_prompt
    assert "разные сущности" in system_prompt
    assert "товарные поля" in system_prompt
    assert "условные" in system_prompt
