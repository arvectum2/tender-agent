from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shared.db.base import Base
from src.tender_research.config import TenderResearchConfig
from src.tender_research.errors import (
    DocumentIdentityConflictError,
    EisConnectionResetError,
    IngestCheckpointConflictError,
)
from src.tender_research.ingest_checkpoint import IngestCheckpointStore
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.repository import TenderRepository
from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class _FlakyRegistryLoader:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failed = False

    def fetch_by_registry_number(self, registry_number: str) -> EisTenderRaw | None:
        self.calls.append(registry_number)
        if registry_number == "B" and not self.failed:
            self.failed = True
            raise EisConnectionResetError("temporary source outage")
        return EisTenderRaw(
            external_id=registry_number,
            registry_number=registry_number,
            title=f"Tender {registry_number}",
            application_deadline=datetime(2026, 9, 20, tzinfo=UTC),
            documents=[],
        )

    def fetch_tender_documents(self, tender: EisTenderRaw) -> list[EisDocumentRaw]:
        return []


def test_interrupted_registry_batch_resumes_after_last_committed_item(tmp_path):
    session = _session()
    loader = _FlakyRegistryLoader()
    config = TenderResearchConfig(
        data_dir=str(tmp_path), web_search_enabled=False, web_fetch_enabled=False
    )
    pipeline = TenderResearchPipeline(session, config=config, eis_loader=loader)

    first = pipeline.ingest_eis_by_registry_numbers(
        ["A", "B", "C"], checkpoint_key="daily-eis"
    )

    assert first["saved"] == 1
    assert first["connection_resets"] == 1
    assert first["checkpoint_status"] == "blocked"
    assert first["next_index"] == 1
    assert TenderRepository(session).count_tenders() == 1
    checkpoint = IngestCheckpointStore(tmp_path).load("daily-eis")
    assert checkpoint is not None
    assert checkpoint.next_index == 1
    assert checkpoint.last_external_id == "B"
    assert checkpoint.last_error == "connection_reset"

    resumed = pipeline.ingest_eis_by_registry_numbers(
        ["A", "B", "C"], checkpoint_key="daily-eis"
    )

    assert resumed["resumed_from_index"] == 1
    assert resumed["saved"] == 2
    assert resumed["checkpoint_status"] == "completed"
    assert resumed["next_index"] == 3
    assert loader.calls == ["A", "B", "B", "C"]
    assert TenderRepository(session).count_tenders() == 3


def test_completed_checkpoint_replay_is_idempotent(tmp_path):
    session = _session()
    loader = _FlakyRegistryLoader()
    loader.failed = True
    config = TenderResearchConfig(
        data_dir=str(tmp_path), web_search_enabled=False, web_fetch_enabled=False
    )
    pipeline = TenderResearchPipeline(session, config=config, eis_loader=loader)

    first = pipeline.ingest_eis_by_registry_numbers(
        ["A", "B"], checkpoint_key="stable-batch"
    )
    calls_after_first = list(loader.calls)
    second = pipeline.ingest_eis_by_registry_numbers(
        ["A", "B"], checkpoint_key="stable-batch"
    )

    assert first["checkpoint_status"] == "completed"
    assert second["checkpoint_status"] == "completed"
    assert second["resumed_from_index"] == 2
    assert second["saved"] == 0
    assert loader.calls == calls_after_first
    assert TenderRepository(session).count_tenders() == 2


def test_checkpoint_refuses_different_input_under_same_key(tmp_path):
    store = IngestCheckpointStore(tmp_path)
    store.begin(key="batch", source="eis_registry_numbers", items=["A", "B"])

    with pytest.raises(IngestCheckpointConflictError):
        store.begin(key="batch", source="eis_registry_numbers", items=["A", "C"])


def _revision_meta(revision: int) -> dict:
    return {
        "revision": revision,
        "revision_publication_timestamp": f"16.09.2026 0{revision}:00 (МСК)",
        "revision_source_url": f"https://zakupki.gov.ru/revision/{revision}",
        "revision_active": revision == 2,
        "revision_state": "active" if revision == 2 else "inactive",
    }


def test_changed_revision_with_same_source_document_id_remains_distinct():
    session = _session()
    repo = TenderRepository(session)
    tender = repo.upsert_tender(
        {"source": "eis", "external_id": "T", "title": "Tender"}
    )

    old = repo.upsert_document(
        {
            "tender_id": tender.id,
            "source_document_id": "DOC-1",
            "file_name": "contract.docx",
            "sha256": "old-sha",
            "raw_meta": _revision_meta(1),
        }
    )
    current = repo.upsert_document(
        {
            "tender_id": tender.id,
            "source_document_id": "DOC-1",
            "file_name": "contract.docx",
            "sha256": "new-sha",
            "raw_meta": _revision_meta(2),
        }
    )

    assert old.id != current.id
    assert repo.count_documents() == 2
    assert old.document_identity_source == "source_document_id+revision"
    assert current.document_identity_source == "source_document_id+revision"
    assert old.raw_meta["revision"] == 1
    assert current.raw_meta["revision"] == 2


def test_same_content_hash_across_conflicting_revisions_fails_closed():
    session = _session()
    repo = TenderRepository(session)
    tender = repo.upsert_tender(
        {"source": "eis", "external_id": "T", "title": "Tender"}
    )
    repo.upsert_document(
        {
            "tender_id": tender.id,
            "source_document_id": "DOC-OLD",
            "file_name": "contract.docx",
            "sha256": "same-sha",
            "raw_meta": _revision_meta(1),
        }
    )

    with pytest.raises(DocumentIdentityConflictError):
        repo.upsert_document(
            {
                "tender_id": tender.id,
                "source_document_id": "DOC-NEW",
                "file_name": "contract.docx",
                "sha256": "same-sha",
                "raw_meta": _revision_meta(2),
            }
        )

    assert repo.count_documents() == 1


def test_same_revision_identity_cannot_silently_change_content_hash():
    session = _session()
    repo = TenderRepository(session)
    tender = repo.upsert_tender(
        {"source": "eis", "external_id": "T", "title": "Tender"}
    )
    base = {
        "tender_id": tender.id,
        "source_document_id": "DOC-1",
        "file_name": "spec.pdf",
        "raw_meta": _revision_meta(2),
    }
    repo.upsert_document({**base, "sha256": "first-sha"})

    with pytest.raises(DocumentIdentityConflictError):
        repo.upsert_document({**base, "sha256": "different-sha"})


def test_replayed_tender_metadata_updates_one_row_and_changes_content_fingerprint(
    tmp_path,
):
    session = _session()
    config = TenderResearchConfig(
        data_dir=str(tmp_path), web_search_enabled=False, web_fetch_enabled=False
    )
    loader = _FlakyRegistryLoader()
    loader.failed = True
    pipeline = TenderResearchPipeline(session, config=config, eis_loader=loader)

    pipeline.ingest_eis_by_registry_numbers(["A"], checkpoint_key="snapshot-1")
    repo = TenderRepository(session)
    first = repo.get_tender_by_external("eis", "A")
    assert first is not None
    first_hash = first.content_hash

    original_fetch = loader.fetch_by_registry_number

    def changed_fetch(registry_number: str) -> EisTenderRaw | None:
        raw = original_fetch(registry_number)
        assert raw is not None
        raw.application_deadline = datetime(2026, 9, 21, tzinfo=UTC)
        raw.status = "changed"
        return raw

    loader.fetch_by_registry_number = changed_fetch  # type: ignore[method-assign]
    pipeline.ingest_eis_by_registry_numbers(["A"], checkpoint_key="snapshot-2")

    updated = repo.get_tender_by_external("eis", "A")
    assert updated is not None
    assert repo.count_tenders() == 1
    assert updated.application_deadline is not None
    assert updated.application_deadline.replace(tzinfo=UTC) == datetime(2026, 9, 21, tzinfo=UTC)
    assert updated.status == "changed"
    assert updated.content_hash != first_hash
