from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.rag.cli import main
from src.tender_research.rag.embeddings import BaseEmbeddingProvider
from src.tender_research.rag.llm import RagAnswer, build_source_citations
from src.tender_research.repository import TenderRepository


@pytest.fixture(autouse=True)
def explicit_legacy_backend_for_legacy_cli_tests(monkeypatch):
    monkeypatch.setenv("AI_CORP_RAG_RETRIEVAL_BACKEND", "legacy")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "fake"
    model_name = "fake-model"
    dimension = 2

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append([
                1.0 if "заявк" in lowered else 0.0,
                1.0 if "оплат" in lowered else 0.0,
            ])
        return vectors


def _seed_db(db_url: str, text_path: Path) -> None:
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = TenderRepository(session)
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "t-1",
            "registry_number": "123",
            "title": "Тестовая закупка",
            "customer_name": "Тестовый заказчик",
        }
    )
    repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "spec.txt",
            "text_extraction_status": "extracted",
            "extracted_text_path": str(text_path),
        }
    )
    session.commit()
    session.close()


def _prepare_index(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "rag.sqlite"
    db_url = f"sqlite:///{db_path}"
    text_path = tmp_path / "spec.txt"
    text_path.write_text(
        ("Требования к составу заявки. Условия оплаты по контракту. " * 40).strip(),
        encoding="utf-8",
    )
    _seed_db(db_url, text_path)

    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(tmp_path / "vectors.json"))
    monkeypatch.setenv("AI_CORP_RAG_EMBEDDINGS_PROVIDER", "hashing")
    get_settings.cache_clear()

    monkeypatch.setattr(
        "src.tender_research.rag.cli.build_embedding_provider",
        lambda config: FakeEmbeddingProvider(),
    )

    monkeypatch.setattr("sys.argv", ["rag", "build-chunks", "--limit", "10"])
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "build-embeddings",
            "--provider",
            "local_hash",
            "--model",
            "local-hash-v1",
            "--limit",
            "10",
        ],
    )
    main()
    capsys.readouterr()


def test_rag_ask_cli_retrieval_only_default(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    monkeypatch.setattr(
        "sys.argv",
        ["rag", "ask", "--registry-number", "123", "--question", "Какие требования к составу заявки?"],
    )
    main()
    out = capsys.readouterr().out

    assert "answer_mode: retrieval_only" in out
    assert "LLM не использовалась. Ниже релевантные фрагменты." in out
    assert "retrieval_provider:" in out
    assert "document_file_name: spec.txt" in out
    assert "chunk_id:" in out


def test_rag_ask_cli_use_llm_calls_mocked_client(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)
    observed: dict[str, object] = {"called": False}

    class FakeClient:
        def generate_answer(self, question, contexts, registry_number=None):
            observed["called"] = True
            observed["question"] = question
            observed["registry_number"] = registry_number
            return RagAnswer(
                answer="Краткий ответ:\nТребования к составу заявки найдены.\n\nИсточники:\n1. spec.txt, chunk_id=chunk-1, registry_number=123",
                sources=build_source_citations(contexts),
                used_chunks_count=len(contexts),
                model="qwen-local",
            )

    monkeypatch.setattr("src.tender_research.rag.cli._build_local_llm_client", lambda config: FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "ask",
            "--registry-number",
            "123",
            "--question",
            "Какие требования к составу заявки?",
            "--use-llm",
            "--llm-model",
            "qwen-local",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert observed["called"] is True
    assert observed["registry_number"] == "123"
    assert "answer_mode: local_llm" in out
    assert "llm_model: qwen-local" in out
    assert "Требования к составу заявки найдены." in out
    assert "document_file_name: spec.txt" in out


def test_rag_ask_cli_insufficient_context_skips_llm(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)
    observed = {"called": False}

    class FakeClient:
        def generate_answer(self, question, contexts, registry_number=None):
            observed["called"] = True
            raise AssertionError("LLM should not be called without context hits")

    monkeypatch.setattr("src.tender_research.rag.cli._build_local_llm_client", lambda config: FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "ask",
            "--registry-number",
            "999",
            "--question",
            "Какие требования к составу заявки?",
            "--use-llm",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert observed["called"] is False
    assert "context_hits: 0" in out
    assert "Контекст не найден в локальном индексе." in out


def test_rag_ask_cli_llm_unavailable_falls_back_to_sources(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    class FakeClient:
        def generate_answer(self, question, contexts, registry_number=None):
            return RagAnswer(
                answer="",
                sources=build_source_citations(contexts),
                used_chunks_count=len(contexts),
                model="qwen-local",
                error="Local LLM server is unavailable: refused",
            )

    monkeypatch.setattr("src.tender_research.rag.cli._build_local_llm_client", lambda config: FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "ask",
            "--registry-number",
            "123",
            "--question",
            "Какие требования к составу заявки?",
            "--use-llm",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert "answer_mode: retrieval_fallback" in out
    assert "llm_error: Local LLM server is unavailable: refused" in out
    assert "LLM недоступна или не вернула корректный ответ. Ниже релевантные фрагменты." in out
    assert "document_file_name: spec.txt" in out
