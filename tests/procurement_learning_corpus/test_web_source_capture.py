"""Offline source metadata capture along the real saved-page transaction."""
from __future__ import annotations

import copy
import hashlib
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.web_source_capture import (
    make_fetched_web_source_candidate,
)
from src.tender_research.config import TenderResearchConfig
from src.tender_research.models import ProcurementTender, ProcurementWebPage
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.repository import TenderRepository
from src.tender_research.schemas import FetchResult


def fetched(**overrides):
    url = "https://public.example.org/tenders/123/"
    defaults = {
        "url": url,
        "normalized_url": url,
        "url_hash": hashlib.sha256(url.encode()).hexdigest(),
        "status": "fetched",
        "http_status": 200,
        "content_type": "text/html; charset=utf-8",
        "final_url": url,
        "html": "<html><title>sample</title>Original public evidence</html>",
        "extracted_text": "Original public evidence",
        "extracted_title": "sample",
    }
    return FetchResult(**{**defaults, **overrides})


def test_source_metadata_contains_no_raw_page_url_text_or_claims():
    case = fetched()
    row = make_fetched_web_source_candidate("0372200172326000015", case)
    assert row is not None
    payload = row["payload_json"]
    assert row["event_kind"] == "manual_review"
    assert row["visibility_scope"] == "owner_internal"
    assert row["training_status"] == "candidate_unreviewed"
    assert row["candidate_split"] == "manual_candidate_not_blind"
    assert payload["source_host"] == "public.example.org"
    assert payload["source_decoded_html_sha256"] == hashlib.sha256(
        case.html.encode()
    ).hexdigest()
    assert payload["source_html_bytes"] == len(case.html.encode())
    assert payload["human_verified_interpretation"] is False
    assert payload["owner_bid_go"] is False
    assert payload["original_source_verification_gate"].startswith("PUBLIC_FETCH_ONLY")
    serialized = str(payload)
    assert case.html not in serialized
    assert case.extracted_text not in serialized
    assert case.url not in serialized


@pytest.mark.parametrize(("field", "value"), [
    ("url", "http://public.example.org/tenders/123/"),
    ("url", "https://user:pass@public.example.org/tenders/123/"),
    ("url", "https://public.example.org/tenders/123/?access_token=sensitive"),
    ("url", "https://public.example.org/tenders/123/#private"),
    ("url", "https://127.0.0.1/tenders/123/"),
    ("url", "https://localhost/tenders/123/"),
    ("url", "https://private.local/tenders/123/"),
    ("url", "https://10.0.0.1/tenders/123/"),
    ("url", "https://public.example.org:8443/tenders/123/"),
    ("status", "timeout"),
    ("status", "blocked"),
    ("http_status", 404),
    ("http_status", 302),
    ("content_type", "application/pdf"),
    ("html", ""),
    ("html", None),
    ("html", "Z" * (4 * 1024 * 1024 + 1)),
    ("final_url", "https://notpublic.example.org/tenders/123/"),
    ("final_url", "http://public.example.org/tenders/123/"),
])
def test_unsafe_or_nonverified_web_hits_never_enter_learning_corpus(field, value):
    assert make_fetched_web_source_candidate(
        "0372200172326000015", fetched(**{field: value})
    ) is None


def test_identical_fetched_html_replay_same_id_content_changes_new_version():
    a = fetched()
    before = make_fetched_web_source_candidate("0372200172326000015", a)
    assert before == make_fetched_web_source_candidate(
        "0372200172326000015", copy.deepcopy(a)
    )
    changed = make_fetched_web_source_candidate(
        "0372200172326000015",
        fetched(html=a.html.replace("sample", "updated")),
    )
    assert changed["observation_id"] != before["observation_id"]
    assert changed["procurement_ref"] == before["procurement_ref"]


def _prepare_pipeline(session, tmp_path, *, outcome):
    repo = TenderRepository(session)
    tender = repo.upsert_tender({
        "source": "eis", "external_id": "0372200172326000015",
        "registry_number": "0372200172326000015", "title": "Museum public tender",
    })
    query = repo.upsert_search_query({
        "tender_id": tender.id, "query": "Museum", "query_type": "public",
        "provider": "duckduckgo_html",
    })
    page = fetched()
    repo.upsert_search_result({
        "tender_id": tender.id,
        "query_id": query.id,
        "provider": query.provider,
        "rank": 1,
        "title": "Original",
        "url": page.url,
        "normalized_url": page.normalized_url,
        "snippet": "Example snippet, never learning gold",
        "url_hash": page.url_hash,
    })
    session.commit()
    fetcher = MagicMock()
    fetcher.fetch.return_value = outcome
    config = TenderResearchConfig(
        data_dir=str(tmp_path),
        web_fetch_enabled=True,
        web_fetch_delay_seconds=0,
    )
    pipeline = TenderResearchPipeline(
        session, config=config, eis_loader=MagicMock(), web_fetcher=fetcher,
    )
    return pipeline, tender


def test_pipeline_public_html_atomic_capture(session, tmp_path, monkeypatch):
    monkeypatch.delenv("TENDER_LEARNING_CAPTURE_ENABLED", raising=False)
    pipeline, tender = _prepare_pipeline(session, tmp_path, outcome=fetched())
    result = pipeline.fetch_search_results(tender.id, max_pages=1)
    assert result == {"fetched": 1, "failed": 0}
    rows = session.scalars(select(ProcurementLearningObservation)).all()
    pages = session.scalars(select(ProcurementWebPage)).all()
    assert len(pages) == 1
    assert len(rows) == 1
    assert pages[0].fetch_status == "fetched"
    assert rows[0].payload_json["source_decoded_html_sha256"] == hashlib.sha256(
        fetched().html.encode()
    ).hexdigest()
    assert rows[0].training_status == "candidate_unreviewed"
    assert rows[0].procurement_ref == tender.registry_number
    assert pipeline.fetch_search_results(tender.id) == {"fetched": 0, "failed": 0}
    assert session.query(ProcurementLearningObservation).count() == 1


def test_failed_fetch_not_promoted(session, tmp_path, monkeypatch):
    monkeypatch.delenv("TENDER_LEARNING_CAPTURE_ENABLED", raising=False)
    pipeline, tender = _prepare_pipeline(
        session, tmp_path, outcome=fetched(status="failed", http_status=500, html=None)
    )
    result = pipeline.fetch_search_results(tender.id)
    assert result == {"fetched": 0, "failed": 1}
    assert session.query(ProcurementWebPage).count() == 1
    assert session.query(ProcurementLearningObservation).count() == 0


def test_disabled_capture_keeps_page(session, tmp_path, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "0")
    pipeline, tender = _prepare_pipeline(session, tmp_path, outcome=fetched())
    result = pipeline.fetch_search_results(tender.id)
    assert result["fetched"] == 1
    assert session.query(ProcurementWebPage).count() == 1
    assert session.query(ProcurementLearningObservation).count() == 0


def test_bad_capture_setting_rolls_back_fetched_page(session, tmp_path, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "maybe")
    pipeline, tender = _prepare_pipeline(session, tmp_path, outcome=fetched())
    with pytest.raises(ValueError, match="0 or 1"):
        pipeline.fetch_search_results(tender.id)
    assert session.query(ProcurementWebPage).count() == 0
    assert session.query(ProcurementLearningObservation).count() == 0
    assert session.query(ProcurementTender).count() == 1


def test_append_failure_rolls_back_page(session, tmp_path, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "1")
    pipeline, tender = _prepare_pipeline(session, tmp_path, outcome=fetched())
    from src.tender_research import pipeline as pipeline_module

    def fail_candidate(_session, _candidate):
        raise RuntimeError("Learning DB missing or corrupted")

    monkeypatch.setattr(pipeline_module, "append_candidate", fail_candidate)
    with pytest.raises(RuntimeError, match="Learning DB"):
        pipeline.fetch_search_results(tender.id)
    assert session.query(ProcurementWebPage).count() == 0
    assert session.query(ProcurementLearningObservation).count() == 0
