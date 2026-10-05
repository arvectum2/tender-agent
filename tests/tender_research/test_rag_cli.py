from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.rag.cli import main
from src.tender_research.rag.embeddings import BaseEmbeddingProvider
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


def test_rag_cli_build_chunks_and_search_smoke(tmp_path, monkeypatch, capsys):
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
    build_chunks_out = capsys.readouterr().out
    assert "chunks_created:" in build_chunks_out

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
    build_embeddings_out = capsys.readouterr().out
    assert "embeddings_created:" in build_embeddings_out

    monkeypatch.setattr(
        "sys.argv",
        ["rag", "search", "--query", "состав заявки", "--limit", "5"],
    )
    main()
    search_out = capsys.readouterr().out
    assert "hits:" in search_out
    assert "registry_number: 123" in search_out


def test_rag_cli_embedding_flags_override_config(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "rag.sqlite"
    db_url = f"sqlite:///{db_path}"
    text_path = tmp_path / "spec.txt"
    text_path.write_text("Требования к составу заявки.", encoding="utf-8")
    _seed_db(db_url, text_path)

    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    monkeypatch.setenv("AI_CORP_ARVECTUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_CORP_RAG_VECTOR_STORE_PATH", str(tmp_path / "vectors.json"))
    monkeypatch.setenv("AI_CORP_RAG_EMBEDDINGS_PROVIDER", "hashing")
    monkeypatch.setenv("AI_CORP_RAG_EMBEDDINGS_MODEL", "env-default-model")
    get_settings.cache_clear()

    observed: dict[str, str] = {}

    def fake_build_embedding_provider(config):
        observed["provider"] = config.rag_embeddings_provider
        observed["model"] = config.rag_embeddings_model
        return FakeEmbeddingProvider()

    monkeypatch.setattr("src.tender_research.rag.cli.build_embedding_provider", fake_build_embedding_provider)

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

    assert observed == {"provider": "local_hash", "model": "local-hash-v1"}
