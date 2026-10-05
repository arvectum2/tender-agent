from __future__ import annotations

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


class _FixedEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, provider_name: str, model_name: str):
        self.provider_name = provider_name
        self.model_name = model_name
        self.dimension = 2

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _seed_repo(tmp_path) -> tuple[str, Path]:
    db_path = tmp_path / "selection.sqlite"
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

    root_store = Path(tmp_path) / "vectors.json"
    local_store = JsonVectorStore(root_store, dimension=2)
    local_store.upsert(chunk.id, [1.0, 0.0], {"chunk_id": chunk.id})
    local_store.persist()
    repo.upsert_document_embedding(
        {
            "chunk_id": chunk.id,
            "provider": "hashing",
            "model": "local-hash-v1",
            "dimension": 2,
            "vector_id": chunk.id,
            "embedding_path": str(local_store.path),
            "embedding_hash": "local",
        }
    )

    llama_store = JsonVectorStore(Path(tmp_path) / "vectors__llama_cpp__qwen3_embedding_4b.json", dimension=2)
    llama_store.upsert(chunk.id, [1.0, 0.0], {"chunk_id": chunk.id})
    llama_store.persist()
    repo.upsert_document_embedding(
        {
            "chunk_id": chunk.id,
            "provider": "llama_cpp",
            "model": "Qwen3-Embedding-4B",
            "dimension": 2,
            "vector_id": chunk.id,
            "embedding_path": str(llama_store.path),
            "embedding_hash": "llama",
        }
    )
    session.commit()
    session.close()
    return db_url, root_store


def test_local_hash_and_llama_cpp_embeddings_coexist_and_search_selects_model(tmp_path, monkeypatch, capsys):
    db_url, root_store = _seed_repo(tmp_path)
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(root_store))
    get_settings.cache_clear()

    def fake_build_embedding_provider(config):
        provider = (config.rag_embeddings_provider or "").lower()
        if provider in {"hashing", "local_hash"}:
            return _FixedEmbeddingProvider("hashing", "local-hash-v1")
        return _FixedEmbeddingProvider("llama_cpp", "Qwen3-Embedding-4B")

    monkeypatch.setattr("src.tender_research.rag.cli.build_embedding_provider", fake_build_embedding_provider)

    monkeypatch.setattr("sys.argv", ["rag", "search", "--query", "состав заявки", "--provider", "local_hash"])
    main()
    local_out = capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "search",
            "--query",
            "состав заявки",
            "--provider",
            "llama_cpp",
            "--model",
            "Qwen3-Embedding-4B",
        ],
    )
    main()
    llama_out = capsys.readouterr().out

    assert "provider: local_hash" in local_out
    assert "hits: 1" in local_out
    assert "provider: llama_cpp" in llama_out
    assert "model: Qwen3-Embedding-4B" in llama_out
    assert "hits: 1" in llama_out


def test_search_reports_missing_embeddings_clearly(tmp_path, monkeypatch, capsys):
    db_url, root_store = _seed_repo(tmp_path)
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(root_store))
    get_settings.cache_clear()

    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "search",
            "--query",
            "состав заявки",
            "--provider",
            "llama_cpp",
            "--model",
            "BGE-M3",
        ],
    )
    main()
    out = capsys.readouterr().out

    assert "No embeddings found for provider=llama_cpp model=BGE-M3. Run build-embeddings first." in out
