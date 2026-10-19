"""One genuine, distinct archived-source Gemma RAG quality rerun after indexing.

Not a new tender discovery or duplicate source_queue completion. Requires a
correct preconfigured canonical owner runtime, complete originals, Data
Platform collection, local Gemma and restorable full PostgreSQL backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.procurement_llm.analysis_queue_worker import (
    QUALITY_GEMMA_LLAMA_BASE_URL,
    QUALITY_GEMMA_LLAMA_MODEL,
    PinnedSource,
    WorkerGateError,
    readiness,
    source_rows,
)
from scripts.procurement_llm.import_candidates import _engine_url
from scripts.procurement_llm.prepare_eis_original_documents import (
    verify_registered_exact_source_set,
)
from scripts.procurement_llm.source_pipeline_runtime import (
    fresh_pg_backup,
    single_runner,
)
from src.tender_research.config import load_config
from src.tender_research.models import TenderAnalysisRun
from src.tender_research.rag.analysis_service import analyze_tender
from src.tender_research.rag.data_platform import (
    build_data_platform_client,
    build_tender_collection_id,
)
from src.tender_research.repository import TenderRepository

NUMBER = "0163200000326005243"
SOURCE = "source_quality_rerun"
MAX_REPORT_BYTES = 600_000


def source_for_case(session: Session, number: str) -> PinnedSource:
    if number != NUMBER:
        raise WorkerGateError("quality rerun only pinned archival Smolensk case")
    sources = [
        row for row in source_rows(session)
        if row.procurement_ref == number and row.platform == "eis"
    ]
    if len(sources) != 1:
        raise WorkerGateError("pinned original EIS snapshot not unique")
    src = sources[0]
    proof = verify_registered_exact_source_set(session, src.procurement_ref)
    if (
        proof["original_archive_sha256"] != src.original_sha256
        or proof["registered_documents_verified"] != 6
    ):
        raise WorkerGateError("six immutable originals not verified")
    return src


def existing_rerun(session: Session, number: str) -> bool:
    return (
        session.scalar(
            select(TenderAnalysisRun.id)
            .where(
                TenderAnalysisRun.registry_number == number,
                TenderAnalysisRun.source == SOURCE,
            ).limit(1)
        ) is not None
    )


def run_quality_once(session: Session, *, number: str = NUMBER) -> dict:
    src = source_for_case(session, number)
    if existing_rerun(session, number):
        return {
            "status": "already_recorded_no_duplicate_run",
            "ref": number,
            "new_model_calls": 0,
            "no_training_gold": True,
        }
    ready = readiness(
        session, src,
        require_services=True,
        llm_base_url=QUALITY_GEMMA_LLAMA_BASE_URL,
        llm_model=QUALITY_GEMMA_LLAMA_MODEL,
    )
    if not ready["ready_for_actual_llm"]:
        raise WorkerGateError(
            "source-bound indexed Data Platform + Gemma not ready: "
            + ",".join(ready["blockers"])
        )
    before_ids = set(
        session.scalars(
            select(TenderAnalysisRun.id).where(
                TenderAnalysisRun.registry_number == number
            )
        ).all()
    )
    result = analyze_tender(
        number,
        session=session,
        use_llm=True,
        save_report=True,
        record_history=True,
        history_source=SOURCE,
        analysis_mode="detailed",
        llm_timeout_seconds=420,
        llm_base_url=QUALITY_GEMMA_LLAMA_BASE_URL,
        llm_model=QUALITY_GEMMA_LLAMA_MODEL,
    )
    if not result.run_id:
        raise WorkerGateError("actual Gemma RAG analysis did not persist history")
    run = session.get(TenderAnalysisRun, result.run_id)
    if (
        run is None or run.id in before_ids
        or run.registry_number != number
        or run.source != SOURCE
        or not run.used_llm
        or run.llm_model != QUALITY_GEMMA_LLAMA_MODEL
    ):
        raise WorkerGateError("new source quality history is not genuine")
    report = Path(result.report_path) if result.report_path else None
    reports_root = (Path(load_config().data_dir) / "rag" / "reports").resolve()
    if (
        report is None or report.is_symlink() or not report.is_file()
        or not report.resolve().is_relative_to(reports_root)
        or not 0 < report.stat().st_size <= MAX_REPORT_BYTES
    ):
        raise WorkerGateError("quality report missing or outside private RAG folder")
    report.chmod(0o600)
    if stat.S_IMODE(report.stat().st_mode) != 0o600:
        raise WorkerGateError("quality report not owner-private")
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest()
    # The observed run is traceable to this exact archived original ZIP; a
    # second source_queue completion event is deliberately NOT appended.
    metadata = json.loads(run.metadata_json) if run.metadata_json else {}
    if not isinstance(metadata, dict):
        raise WorkerGateError("run metadata invalid")
    all_sections_cited = bool(
        result.sections and all(
            section.status == "completed" and bool(section.sources)
            for section in result.sections
        )
    )
    metadata["archival_quality_recheck"] = {
        "schema": "source_sha_bound_gemma_quality_rerun_v1",
        "source_observation_id": src.observation_id,
        "source_original_zip_sha256": src.original_sha256,
        "report_sha256": report_sha,
        "originals_verified": 6,
        "llm_real_run": True,
        "all_sections_source_cited": all_sections_cited,
        "legal_status_verified": False,
        "training_gold": False,
        "bid_go": False,
        "second_source_completion": False,
    }
    run.metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    session.commit()
    return {
        "status": "actual_quality_history_recorded",
        "ref": number,
        "run_id": str(run.id),
        "llm_model": run.llm_model,
        "sections": result.sections_count,
        "sections_strictly_cited": sum(
            s.status == "completed" and bool(s.sources) for s in result.sections
        ),
        "duration_seconds": result.duration_seconds,
        "report_sha256": report_sha,
        "report_path": str(report),
        "llm_calls_count": result.llm_calls_count,
        "run_status": result.status,
        "human_gold": False,
        "owner_bid_go": False,
        "independent_chatgpt_review_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", default=NUMBER)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.number != NUMBER:
        parser.error("only approved, pinned original Smolensk case")
    if args.apply and args.confirm_database != "arvectum":
        parser.error("canonical live quality history requires approval")
    with single_runner():
        engine = create_engine(_engine_url())
        try:
            with Session(engine) as session:
                src = source_for_case(session, args.number)
                if existing_rerun(session, args.number):
                    print(json.dumps({
                        "status": "already_recorded_no_duplicate_run",
                        "ref": src.procurement_ref,
                    }))
                    return 0
                if not args.apply:
                    gates = readiness(
                        session, src, require_services=True,
                        llm_base_url=QUALITY_GEMMA_LLAMA_BASE_URL,
                        llm_model=QUALITY_GEMMA_LLAMA_MODEL,
                    )
                    ready = gates.get("ready_for_actual_llm") is True
                    repo = TenderRepository(session)
                    tender = repo.get_tender_by_registry_number(src.procurement_ref)
                    diagnostics = {}
                    if tender is not None:
                        diagnostics["registered_sql_chunks"] = repo.count_chunks_by_tender(tender.id)
                        collection = build_tender_collection_id(repo, tender.id)
                        if collection:
                            client = None
                            try:
                                client = build_data_platform_client(load_config())
                                stats = client.collection_stats(collection)
                                diagnostics["data_platform_resources"] = stats.get("resources")
                                diagnostics["data_platform_embeddings"] = stats.get("embeddings")
                            except Exception:  # noqa: BLE001 - do not leak service credentials
                                diagnostics["data_platform_stats_unavailable"] = True
                            finally:
                                if client is not None:
                                    client.close()
                    print(json.dumps({
                        "status": "read_only_quality_preflight",
                        "ref": src.procurement_ref,
                        "source_archive_sha256": src.original_sha256,
                        "ready_for_actual_llm": ready,
                        "blockers": gates.get("blockers", []),
                        "index_diagnostics": diagnostics,
                        "will_create_new_source_completion": False,
                    }, ensure_ascii=False, sort_keys=True))
                    return 0 if ready else 2
            backup = fresh_pg_backup()
            with Session(engine) as session:
                result = run_quality_once(session, number=args.number)
            result["fresh_verified_backup_sha256"] = backup["sha256"]
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] in {
                "actual_quality_history_recorded",
                "already_recorded_no_duplicate_run",
            } else 2
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
