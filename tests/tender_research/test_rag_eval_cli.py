from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.rag.cli import main
from src.tender_research.rag.embeddings import BaseEmbeddingProvider
from src.tender_research.rag.vector_store import JsonVectorStore
from src.tender_research.repository import TenderRepository


@pytest.fixture(autouse=True)
def explicit_legacy_backend_for_legacy_cli_tests(monkeypatch):
    monkeypatch.setenv("AI_CORP_RAG_RETRIEVAL_BACKEND", "legacy")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _EvalProvider(BaseEmbeddingProvider):
    provider_name = "hashing"
    model_name = "local-hash-v1"
    dimension = 2

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _seed_eval_runtime(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "eval.sqlite"
    db_url = f"sqlite:///{db_path}"
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
    document = repo.upsert_document({"tender_id": tender.id, "file_name": "spec.txt"})
    chunk = repo.upsert_document_chunk(
        {
            "tender_id": tender.id,
            "document_id": document.id,
            "chunk_index": 0,
            "text": "Требования к содержанию и составу заявки.",
            "text_hash": "chunk-1",
            "char_start": 0,
            "char_end": 40,
            "token_estimate": 8,
            "source_file_name": "spec.txt",
        }
    )

    vector_store = JsonVectorStore(Path(tmp_path) / "vectors.json", dimension=2)
    vector_store.upsert(chunk.id, [1.0, 0.0], {"chunk_id": chunk.id})
    vector_store.persist()
    repo.upsert_document_embedding(
        {
            "chunk_id": chunk.id,
            "provider": "hashing",
            "model": "local-hash-v1",
            "dimension": 2,
            "vector_id": chunk.id,
            "embedding_path": str(vector_store.path),
            "embedding_hash": "hash",
        }
    )
    session.commit()
    session.close()

    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(vector_store.path))
    get_settings.cache_clear()

    return Path("tests/fixtures/tender_research/rag_eval_questions.json")


def test_eval_cli_loads_questions_writes_jsonl_and_reports_summary(tmp_path, monkeypatch, capsys):
    questions_path = _seed_eval_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("src.tender_research.rag.cli.build_embedding_provider", lambda config: _EvalProvider())
    monkeypatch.setattr(
        "sys.argv",
        ["rag", "eval", "--questions", str(questions_path), "--provider", "local_hash", "--limit", "3"],
    )

    main()
    out = capsys.readouterr().out

    assert "questions_total: 20" in out
    assert "questions_with_results:" in out
    assert "provider: local_hash" in out

    output_line = next(line for line in out.splitlines() if line.startswith("output_path: "))
    output_path = Path(output_line.split(": ", 1)[1])
    assert output_path.exists()
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 20
    assert rows[0]["provider"] == "local_hash"
