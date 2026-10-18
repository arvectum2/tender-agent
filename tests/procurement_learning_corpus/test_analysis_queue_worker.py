"""Real LLM-only analysis worker and immutable source-version completion gates."""
from __future__ import annotations

import hashlib
import stat
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.procurement_llm import analysis_queue_worker as w
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
)
from src.tender_research.models import TenderAnalysisRun
from src.tender_research.rag.schemas import (
    SourceCitation,
    TenderAnalysisResult,
    TenderAnalysisSection,
)

NUMBER = "0163200000326005243"


def private_source(tmp_path, *, number=NUMBER, original=b"EIS source archival bytes"):
    root = tmp_path / "private"
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    sha = hashlib.sha256(original).hexdigest()
    folder = root / "original-snapshots" / "eis" / number
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    path = folder / (sha + ".zip")
    path.write_bytes(original)
    path.chmod(0o600)
    return root, sha, path


def insert_source(session, tmp_path, *, ref=NUMBER, original=b"EIS source archival bytes",
                  platform="eis"):
    root, sha, path = private_source(tmp_path, number=ref, original=original)
    event = {
        "event_id": "ta-eis-zip:" + sha[:28] if platform == "eis"
        else "ta-firstparty:" + sha[:28],
        "procurement_ref": ref,
        "source_platform": platform,
        "participation": "reviewed_only",
        "review_state": "source_documented",
        "source_role": "development_exposed",
        "official_archive_sha256": sha if platform == "eis" else None,
        "original_zip_owner_private_path": str(path) if platform == "eis" else None,
        "training_labels": "NOT_REVIEWED",
        "owner_bid_go": False,
    }
    row = make_manual_candidate(event)
    assert append_candidate(session, row)
    session.commit()
    src = w.source_rows(session)[0]
    assert src.original_sha256 == sha
    return root, src, path


def fake_analysis(run_id, report_path, *, status="completed",
                  section_status="completed", used_llm=True, sources=1):
    citation = SourceCitation(
        chunk_id="chunk-1", registry_number=NUMBER,
        tender_title="EIS", customer_name=None, document_id="doc-1",
        document_file_name="official.xml", score=0.97, quote_preview="Original",
    )
    return TenderAnalysisResult(
        status=status,
        registry_number=NUMBER,
        sections=[TenderAnalysisSection(
            id="notice_info", title="Notice", question="What?", answer="cited",
            sources=[citation] if sources else [], status=section_status,
        )],
        sections_count=1, sources_count=sources, used_llm=used_llm,
        llm_model="qwen2.5-14b", llm_calls_count=1 if used_llm else 0,
        report_path=str(report_path), report_markdown="# Real model output",
        run_id=run_id,
    )


def test_private_sha_read_and_no_tender_blocks_real_llm(session, tmp_path):
    root, src, _ = insert_source(session, tmp_path)
    w.attest_source(src, root=root)
    out = w.readiness(session, src, root=root, require_services=True)
    assert out["status"] == "blocked"
    assert out["blockers"] == ["eis_tender_not_ingested_into_tender_research"]
    assert out["ready_for_actual_llm"] is False


def test_source_tampering_and_private_permissions_prevent_processing(session, tmp_path):
    root, src, path = insert_source(session, tmp_path)
    path.write_bytes(b"TAMPERED")
    with pytest.raises(w.WorkerGateError, match="SHA"):
        w.attest_source(src, root=root)
    out = w.readiness(session, src, root=root)
    assert out["blockers"] == ["source_private_sha_or_access_not_verified"]
    path.write_bytes(b"EIS source archival bytes")
    path.chmod(0o644)
    with pytest.raises(w.WorkerGateError, match="0600"):
        w.attest_source(src, root=root)


def test_original_symlink_refused(session, tmp_path):
    root, src, path = insert_source(session, tmp_path)
    other = path.with_suffix(".tmp")
    path.rename(other)
    path.symlink_to(other)
    with pytest.raises(w.WorkerGateError, match="invalid"):
        w.attest_source(src, root=root)


def test_marketplace_original_cannot_impersonate_prepared_eis(session, tmp_path):
    root, src, _ = insert_source(session, tmp_path, ref="workspace:19043")
    # Change test fixture from exact EIS file to an HTML path; no source
    # actually becomes analyzable just because a same-title HTML is present.
    src = w.PinnedSource(
        observation_id=src.observation_id, procurement_ref="workspace:19043",
        event_kind="manual:ta-firstparty:abcd",
        original_sha256=src.original_sha256, path=src.path,
        platform="marketplace",
    )
    result = w.readiness(session, src, root=root, require_services=True)
    assert result["ready_for_actual_llm"] is False


def test_readonly_queue_never_runs_analyzer(session, tmp_path):
    root, _src, _ = insert_source(session, tmp_path)
    invoked = Mock(side_effect=AssertionError("never run fake LLM"))
    result = w.work_cycle(
        session, root=root, apply=False, analyzer=invoked,
    )
    assert result["pending_source_versions"] == 1
    assert result["blocked_source_versions"] == 1
    assert result["genuine_completed_analyses"] == 0
    invoked.assert_not_called()


def test_explicit_apply_does_not_run_without_index_and_preparation(session, tmp_path):
    root, _, _ = insert_source(session, tmp_path)
    invoked = Mock(side_effect=AssertionError("not ready!"))
    result = w.work_cycle(session, root=root, apply=True, analyzer=invoked)
    assert result["genuine_completed_analyses"] == 0
    assert result["attempts"] == []
    assert result["readiness"][0]["blockers"] == [
        "eis_tender_not_ingested_into_tender_research"
    ]
    invoked.assert_not_called()


@pytest.mark.parametrize(("status", "section_status", "used_llm", "sources"), [
    ("no_context", "no_context", False, 0),
    ("failed", "completed", True, 1),
    ("completed_with_warnings", "retrieval_only_fallback", True, 1),
    ("completed", "retrieval_only_fallback", True, 1),
    ("completed", "completed", False, 1),
    ("completed", "completed", True, 0),
])
def test_fake_or_fallback_run_never_closes_source(status, section_status, used_llm, sources):
    result = fake_analysis(
        "analyser-id", Path("/private/report.md"), status=status,
        section_status=section_status, used_llm=used_llm, sources=sources,
    )
    assert w._real_success(result) is False


def test_genuine_model_cited_source_can_pass_structural_completion(tmp_path):
    assert w._real_success(fake_analysis("analyser-id", tmp_path / "report.md"))


def test_external_local_llm_must_be_really_alive(monkeypatch):
    cfg = SimpleNamespace(local_llm_base_url="http://127.0.0.1:8088/v1",
                          local_llm_model="qwen2.5-14b")
    from urllib.error import URLError

    monkeypatch.setattr(w.urllib.request, "urlopen", Mock(side_effect=URLError("refused")))
    with pytest.raises(w.WorkerGateError, match="unavailable"):
        w.check_llm_endpoint(cfg)


def test_unknown_llm_external_server_url_refused():
    for uri in [
        "http://evil.example/v1", "https://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/admin", "http://127.0.0.1:8088/v1?token=secret",
    ]:
        cfg = SimpleNamespace(local_llm_base_url=uri, local_llm_model="x")
        with pytest.raises(w.WorkerGateError, match="loopback"):
            w.check_llm_endpoint(cfg)


def test_forged_completion_event_does_not_close_queue(session, tmp_path):
    _root, src, _ = insert_source(session, tmp_path)
    fake = make_manual_candidate({
        "event_id": "ta-ready-analysis:" + src.observation_id[:30],
        "procurement_ref": NUMBER,
        "source_observation_id": src.observation_id,
        "source_original_sha256": src.original_sha256,
        "run_id": str(uuid.uuid4()),
        "actual_llm_run_verified": True,
    })
    assert append_candidate(session, fake)
    session.commit()
    assert w.completed_source_versions(session) == set()


def test_verified_real_saved_run_and_report_bound_to_exact_source(session, tmp_path,
                                                                 monkeypatch):
    root, src, _ = insert_source(session, tmp_path)
    output = tmp_path / "data" / "rag" / "reports"
    output.mkdir(parents=True)
    file = output / "report.md"
    file.write_text("# Genuine grounded LLM report", encoding="utf8")
    monkeypatch.setattr(w, "load_config", lambda: SimpleNamespace(data_dir=str(tmp_path / "data")))
    stored = TenderAnalysisRun(
        registry_number=NUMBER, status="completed", used_llm=True,
        sources_count=1, sections_count=1, llm_model="qwen2.5-14b",
        source="source_queue", report_path=str(file),
    )
    session.add(stored)
    session.commit()
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    assert w.append_source_link(session, src, stored, sha)
    session.commit()
    assert w.completed_source_versions(session) == {src.observation_id}
    assert w.work_cycle(session, root=root, apply=False)["pending_source_versions"] == 0
    file.write_text("# Corrupted afterward", encoding="utf8")
    assert w.completed_source_versions(session) == set()


def test_revised_original_version_reenters_pending_queue(session, tmp_path,
                                                         monkeypatch):
    root, src, _ = insert_source(session, tmp_path)
    output = tmp_path / "data" / "rag" / "reports"
    output.mkdir(parents=True)
    file = output / "report.md"
    file.write_text("Grounded", encoding="utf8")
    monkeypatch.setattr(w, "load_config", lambda: SimpleNamespace(data_dir=str(tmp_path / "data")))
    run = TenderAnalysisRun(
        registry_number=NUMBER, status="completed", used_llm=True,
        sources_count=1, llm_model="qwen2.5-14b",
        source="source_queue", report_path=str(file),
    )
    session.add(run)
    session.commit()
    w.append_source_link(session, src, run, hashlib.sha256(file.read_bytes()).hexdigest())
    session.commit()
    assert w.completed_source_versions(session) == {src.observation_id}
    _, newer, _ = insert_source(session, tmp_path, original=b"New EIS version source bytes")
    assert newer.observation_id != src.observation_id
    result = w.work_cycle(session, root=root, apply=False)
    assert result["pending_source_versions"] == 1
    assert result["readiness"][0]["source_observation_id"] == newer.observation_id


def test_actual_analyzer_must_save_real_run_before_bound_candidate(session, tmp_path,
                                                                  monkeypatch):
    root, src, _ = insert_source(session, tmp_path)
    output = tmp_path / "data" / "rag" / "reports"
    output.mkdir(parents=True)
    report_path = output / "actual.md"
    report_path.write_text("Actual answer with citations", encoding="utf8")
    monkeypatch.setattr(w, "load_config", lambda: SimpleNamespace(data_dir=str(tmp_path / "data")))
    def checker(_session, source, **kwargs):
        return {"ref": source.procurement_ref, "ready_for_actual_llm": True,
                "blockers": [], "status": "ready", "source_observation_id": source.observation_id}
    def analyzer(registry_number, *, session, **kwargs):
        assert registry_number == NUMBER and kwargs["use_llm"] is True
        assert kwargs["record_history"] is True
        row = TenderAnalysisRun(
            registry_number=NUMBER, status="completed", used_llm=True,
            sources_count=1, llm_model="qwen2.5-14b", source="source_queue",
            report_path=str(report_path), sections_count=1,
        )
        session.add(row)
        session.commit()
        return fake_analysis(row.id, report_path)
    result = w.analyse_one(
        session, src, root=root, analyzer=analyzer, checker=checker,
    )
    assert result["status"] == "real_llm_analysis_persisted_and_source_sha_bound"
    assert result["completion_new"] is True
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert w.completed_source_versions(session) == {src.observation_id}
    assert w.work_cycle(session, root=root, apply=False)["pending_source_versions"] == 0


def test_worker_max_actual_bounds(session, tmp_path):
    root, _, _ = insert_source(session, tmp_path)
    with pytest.raises(w.WorkerGateError, match="one or two"):
        w.work_cycle(session, root=root, max_actual=30)
    with pytest.raises(w.WorkerGateError, match="one or two"):
        w.work_cycle(session, root=root, max_actual=True)


def test_same_number_tender_cannot_be_analyzed_without_original_version_binding(
    session, tmp_path
):
    from src.tender_research.models import ProcurementTender

    root, src, _ = insert_source(session, tmp_path)
    tender = ProcurementTender(
        source="eis", external_id=NUMBER, registry_number=NUMBER,
        law_type="44fz", title="Original official EIS archive test",
        raw_payload={"untrusted_placeholder": True},
    )
    session.add(tender)
    session.commit()
    status = w.readiness(session, src, root=root, require_services=True)
    assert status["blockers"] == ["indexed_tender_not_bound_to_source_archive_sha"]
    # Hash binding by itself does NOT imply availability of indexed documents.
    tender.raw_payload = {"owner_attested_original_archive_sha256": src.original_sha256}
    session.commit()
    status = w.readiness(session, src, root=root, require_services=True)
    assert status["blockers"] == ["tender_documents_not_chunked_or_indexed"]


@pytest.mark.parametrize("url", [
    "https://public.example/v1", "http://127.0.0.1:11434/admin",
    "http://127.0.0.1:11434/v1?api_key=secret",
])
def test_untrusted_llm_override_cannot_bypass_local_model_security(
    session, tmp_path, url
):
    root, _, _ = insert_source(session, tmp_path)
    with pytest.raises(w.WorkerGateError, match="local"):
        w.work_cycle(
            session, root=root, apply=True, llm_base_url=url,
            llm_model="qwen3:4b",
        )


def test_worker_cannot_accept_model_without_endpoint(session, tmp_path):
    root, _, _ = insert_source(session, tmp_path)
    with pytest.raises(w.WorkerGateError, match="specified together"):
        w.work_cycle(session, root=root, llm_model="qwen3:4b")
