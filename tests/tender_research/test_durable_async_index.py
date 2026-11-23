"""Crash/restart-safe Tender Agent receipt journal and strict retrieval gate."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.data_platform import DataPlatformError
from src.tender_research.models import TenderAsyncIndexReceipt
from src.tender_research.rag.data_platform import DataPlatformRagRetriever
from src.tender_research.rag.durable_async import (
    AsyncTenderIndexPending,
    DurableTenderAsyncIndex,
    require_existing_background_ready,
)
from tests.tender_research.test_two_mode_ingest import FakeClient, seeded_repo


def test_receipts_survive_restart_and_all_waves_and_gate_search() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    driver = DurableTenderAsyncIndex(repo, client)
    first = driver.advance(tender_id)
    assert first.submitted == 8 and first.running == 8
    assert first.completed == 0 and not first.ready
    assert driver.advance(tender_id).submitted == 8  # no overfilling active queue
    with pytest.raises(AsyncTenderIndexPending):
        driver.require_ready(tender_id)
    with pytest.raises(AsyncTenderIndexPending):
        require_existing_background_ready(
            repo, tender_id, enabled=True, minimum_async_chunks=9
        )

    restarted = type(repo)(Session(bind=repo._session.get_bind()))
    driver2 = DurableTenderAsyncIndex(restarted, client)
    assert driver2.poll(tender_id).submitted == 8
    client.complete_all()
    second = driver2.advance(tender_id)
    assert second.completed == 8 and second.submitted == 9
    client.complete_all()
    assert driver2.require_ready(tender_id) == first.collection_id
    require_existing_background_ready(restarted, tender_id, enabled=True)
    assert len(list(restarted._session.scalars(select(TenderAsyncIndexReceipt)))) == 9
    assert len(client.queued) == 9


def test_failed_and_stale_source_receipts_fail_closed() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    driver = DurableTenderAsyncIndex(repo, client)
    first = driver.advance(tender_id)
    job_id = next(iter(client.jobs))
    client.jobs[job_id]["status"] = "dead_letter"
    assert driver.poll(tender_id).failed == 1
    with pytest.raises(DataPlatformError, match="failed"):
        driver.advance(tender_id)
    with pytest.raises(AsyncTenderIndexPending):
        require_existing_background_ready(repo, tender_id, enabled=True)
    chunk = repo.list_chunks_by_tender(tender_id)[0]
    chunk.text = "synthetic source changed"
    chunk.text_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
    repo._session.commit()
    with pytest.raises(AsyncTenderIndexPending):
        driver.require_ready(tender_id)
    assert first.collection_id != driver._scope(tender_id)[1]


def test_legacy_indexing_remains_ungated_when_feature_disabled() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    require_existing_background_ready(repo, tender_id, enabled=False)
    retriever = DataPlatformRagRetriever(repo, client)
    assert retriever._async_gate_enabled is False
    with pytest.raises(AsyncTenderIndexPending):
        require_existing_background_ready(repo, tender_id, enabled=True)


def test_bad_completion_never_becomes_ready() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    driver = DurableTenderAsyncIndex(repo, client)
    driver.advance(tender_id)
    client.complete_all()
    first_job = next(iter(client.jobs))
    client.jobs[first_job]["result"] = {"chunks": 1}
    with pytest.raises(DataPlatformError, match="no indexed evidence"):
        driver.poll(tender_id)
    with pytest.raises(AsyncTenderIndexPending):
        require_existing_background_ready(repo, tender_id, enabled=True)


def test_pump_advances_only_incomplete_collections_without_starvation() -> None:
    from src.tender_research.rag.async_index_pump import run_one_cycle

    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    driver = DurableTenderAsyncIndex(repo, client)
    assert driver.advance(tender_id).submitted == 8
    result = run_one_cycle(repo, client)
    assert result == {"tenders_seen": 1, "ready": 0, "waiting": 1, "failed": 0}
    assert len(client.queued) == 8
    client.complete_all()
    result = run_one_cycle(repo, client)
    assert result["waiting"] == 1 and len(client.queued) == 9
    client.complete_all()
    result = run_one_cycle(repo, client)
    assert result["ready"] == 1
    assert driver.require_ready(tender_id)
    # Completed collections are not scanned forever, starving new tenders.
    result = run_one_cycle(repo, client)
    assert result == {"tenders_seen": 0, "ready": 0, "waiting": 0, "failed": 0}


def test_opt_in_preparation_submits_waves_without_falsely_marking_ready(
    monkeypatch,
) -> None:
    from contextlib import nullcontext

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag import prepare_service

    repo, _tender_id = seeded_repo(9)
    client = FakeClient()
    config = TenderResearchConfig(rag_async_ingest_enabled=True)
    monkeypatch.setattr(prepare_service, "load_config", lambda: config)
    monkeypatch.setattr(
        prepare_service,
        "build_data_platform_client",
        lambda _config: nullcontext(client),
    )
    monkeypatch.setattr(
        prepare_service,
        "download_tender_documents",
        lambda *_args: {"downloaded": 0, "failed": 0},
    )

    class NoOpProjection:
        def __init__(self, *_args):
            pass

        def build_for_tender(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(
        prepare_service, "DataPlatformDocumentProjector", NoOpProjection
    )
    result = prepare_service.prepare_tender_for_analysis(
        "SYNTHETIC-ASYNC", session=repo._session
    )
    assert result.ready_for_analysis is False
    assert result.status == "completed_with_warnings"
    assert result.steps[-1].status == "pending"
    assert len(client.queued) == 8
    client.complete_all()
    second = prepare_service.prepare_tender_for_analysis(
        "SYNTHETIC-ASYNC", session=repo._session
    )
    assert second.ready_for_analysis is False
    assert len(client.queued) == 9
    client.complete_all()
    third = prepare_service.prepare_tender_for_analysis(
        "SYNTHETIC-ASYNC", session=repo._session
    )
    assert third.ready_for_analysis is True
    assert third.embeddings_total == 9
    assert third.steps[-1].status == "completed"


def test_opt_in_retriever_refuses_partially_indexed_tender_even_if_dp_has_hits() -> (
    None
):
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    retriever = DataPlatformRagRetriever(repo, client, async_gate_enabled=True)
    with pytest.raises(AsyncTenderIndexPending):
        retriever.search_documents("кабель", tender_id=tender_id)
    with pytest.raises(AsyncTenderIndexPending):
        retriever.search_all_documents("кабель")
