from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.rag.cli import main
from src.tender_research.rag.embeddings import BaseEmbeddingProvider
from src.tender_research.rag.llm import RagAnswer, build_source_citations
from src.tender_research.repository import TenderRepository


class FakeEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "fake"
    model_name = "fake-model"
    dimension = 3

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "заявк" in lowered or "документ" in lowered else 0.0,
                    1.0 if "оплат" in lowered or "срок" in lowered else 0.0,
                    1.0 if "штраф" in lowered or "гарант" in lowered else 0.0,
                ]
            )
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
        (
            "Требования к составу заявки и документы участника. "
            "Условия оплаты по контракту и срок поставки товара. "
            "Штрафы, гарантийные обязательства и приёмка товара. "
        )
        * 30,
        encoding="utf-8",
    )
    _seed_db(db_url, text_path)

    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(tmp_path / "vectors.json"))
    monkeypatch.setenv("AI_CORP_RAG_EMBEDDINGS_PROVIDER", "hashing")
    get_settings.cache_clear()

    for target in (
        "src.tender_research.rag.cli.build_embedding_provider",
        "src.tender_research.rag.analysis_service.build_embedding_provider",
    ):
        monkeypatch.setattr(target, lambda config: FakeEmbeddingProvider())

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


def test_analyze_tender_retrieval_only(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    monkeypatch.setattr(
        "sys.argv",
        ["rag", "analyze-tender", "--registry-number", "123", "--limit", "5"],
    )
    main()
    out = capsys.readouterr().out

    assert "# Анализ закупки 123" in out
    assert "Релевантные фрагменты из документов:" in out
    assert "Источники:" in out
    assert "chunk_id:" in out


def test_analyze_tender_use_llm_with_mocked_client(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)
    observed_questions: list[str] = []

    class FakeClient:
        def build_prompt_metrics(self, question, contexts, registry_number=None, analysis_mode="balanced", source_facts=None):
            return {
                "context_chars": 1200,
                "system_prompt_chars": 200,
                "user_prompt_chars": 300,
                "prompt_chars": 500,
            }

        def generate_answer(self, question, contexts, registry_number=None, analysis_mode="balanced", source_facts=None):
            observed_questions.append(question)
            return RagAnswer(
                answer=(
                    "Краткий ответ:\nЕсть релевантные условия.\n\n"
                    "Подробности:\nОтвет сформирован по локальным фрагментам.\n\n"
                    "Источники:\n1. spec.txt, chunk_id=chunk-1, registry_number=123"
                ),
                sources=build_source_citations(contexts),
                used_chunks_count=len(contexts),
                model="qwen-local",
            )

    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.LocalChatLlmClient",
        lambda base_url, model_name, timeout_seconds, max_context_chars: FakeClient(),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "analyze-tender",
            "--registry-number",
            "123",
            "--use-llm",
            "--llm-model",
            "qwen-local",
            "--limit",
            "5",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert len(observed_questions) >= 1
    assert "**LLM:** да (qwen-local)" in out
    assert "Краткий ответ:" in out
    assert "**Источники:**" in out


def test_analyze_tender_output_writes_markdown_file(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)
    output_path = tmp_path / "reports" / "analyze_tender_123.md"

    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "analyze-tender",
            "--registry-number",
            "123",
            "--output",
            str(output_path),
        ],
    )
    main()
    out = capsys.readouterr().out

    assert f"output_path: {output_path}" in out
    content = output_path.read_text(encoding="utf-8")
    assert "# Анализ закупки 123" in content


def test_analyze_tender_registry_filter_applies(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    monkeypatch.setattr(
        "sys.argv",
        ["rag", "analyze-tender", "--registry-number", "999", "--limit", "5"],
    )
    main()
    out = capsys.readouterr().out

    json_line, _, md = out.partition("\n\n")
    payload = json.loads(json_line)
    assert payload["status"] == "no_context"


def test_analyze_tender_llm_unavailable_falls_back_to_retrieval(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    class FakeClient:
        def build_prompt_metrics(self, question, contexts, registry_number=None, analysis_mode="balanced", source_facts=None):
            return {
                "context_chars": 1200,
                "system_prompt_chars": 200,
                "user_prompt_chars": 300,
                "prompt_chars": 500,
            }

        def generate_answer(self, question, contexts, registry_number=None, analysis_mode="balanced", source_facts=None):
            return RagAnswer(
                answer="",
                sources=build_source_citations(contexts),
                used_chunks_count=len(contexts),
                model="qwen-local",
                error="Local LLM server is unavailable: refused",
            )

    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.LocalChatLlmClient",
        lambda base_url, model_name, timeout_seconds, max_context_chars: FakeClient(),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "analyze-tender",
            "--registry-number",
            "123",
            "--use-llm",
            "--limit",
            "5",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert "Релевантные фрагменты из документов:" in out
    assert "chunk_id:" in out


def test_analyze_tender_every_section_has_sources_or_insufficient_info(tmp_path, monkeypatch, capsys):
    _prepare_index(tmp_path, monkeypatch, capsys)

    monkeypatch.setattr(
        "sys.argv",
        ["rag", "analyze-tender", "--registry-number", "123", "--limit", "5"],
    )
    main()
    out = capsys.readouterr().out

    expected_ids = [
        "notice_info", "subject", "customer_requirements",
        "application_composition", "evaluation_criteria", "contract_terms",
        "documentation_requirements", "restrictions_benefits", "deadlines",
        "documents_summary",
    ]
    for sid in expected_ids:
        assert f"## {sid}." in out
    assert out.count("**Источники:**") >= 1

