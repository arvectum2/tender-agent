"""Owner-only source-SHA-bound Tender Agent analysis worker.

One canonical PostgreSQL. Only official EIS originals with a verified SHA,
prepared tender, linked indexed chunks and available local LLM may be analyzed.
An external platform HTML card alone cannot become an LLM research completion.

Dry run is default and makes ZERO database mutations / LLM calls.
Explicit --apply has a real full PostgreSQL prewrite backup. All completions
remain unreviewed candidates, never legal BID_GO or model-gold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.procurement_llm.collect_public_market_originals import OWNER_PRIVATE
from scripts.procurement_llm.import_candidates import _engine_url
from scripts.procurement_llm.source_pipeline_runtime import (
    fresh_pg_backup,
    single_runner,
)
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
)
from src.tender_research.config import load_config
from src.tender_research.models import TenderAnalysisRun
from src.tender_research.rag.analysis_service import analyze_tender
from src.tender_research.rag.data_platform import (
    build_data_platform_client,
    build_tender_collection_id,
)
from src.tender_research.rag.schemas import TenderAnalysisResult
from src.tender_research.repository import TenderRepository

SOURCE_PREFIX = ("manual:ta-eis-zip:", "manual:ta-firstparty:")
COMPLETION_PREFIX = "manual:ta-ready-analysis:"
NUMBER = re.compile(r"[0-9]{19}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_REPORT = 600_000
QUALITY_GEMMA_LLAMA_BASE_URL = "http://127.0.0.1:8081/v1"
QUALITY_GEMMA_LLAMA_MODEL = "arvectum-gemma4-12b-it-qat-q4_0"


class WorkerGateError(ValueError):
    """Required proof, source scope or infrastructure precondition missing."""


@dataclass(frozen=True)
class PinnedSource:
    observation_id: str
    procurement_ref: str
    event_kind: str
    original_sha256: str
    path: Path
    platform: str


def source_rows(session: Session) -> list[PinnedSource]:
    rows = session.scalars(
        select(ProcurementLearningObservation).where(
            ProcurementLearningObservation.visibility_scope == "owner_internal",
            ProcurementLearningObservation.event_kind == "manual_review",
        ).order_by(ProcurementLearningObservation.created_at.desc(),
                   ProcurementLearningObservation.observation_id.desc())
    ).all()
    latest = {}
    for item in rows:
        if not item.source_ref.startswith(SOURCE_PREFIX):
            continue
        if item.training_status != "candidate_unreviewed" or item.customer_id is not None:
            continue
        payload = item.payload_json
        if not isinstance(payload, dict):
            continue
        sha = payload.get("official_archive_sha256") or payload.get(
            "original_html_response_bytes_sha256"
        )
        path = payload.get("original_zip_owner_private_path") or payload.get(
            "source_snapshot_owner_private_path"
        )
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            continue
        if not isinstance(path, str):
            continue
        if item.procurement_ref not in latest:
            latest[item.procurement_ref] = PinnedSource(
                observation_id=item.observation_id,
                procurement_ref=item.procurement_ref,
                event_kind=item.source_ref,
                original_sha256=sha,
                path=Path(path),
                platform="eis" if item.source_ref.startswith(
                    "manual:ta-eis-zip:"
                ) else "marketplace",
            )
    return list(latest.values())


def attest_source(src: PinnedSource, *, root: Path = OWNER_PRIVATE) -> None:
    if (
        not SHA.fullmatch(src.original_sha256)
        or not SHA.fullmatch(src.observation_id)
        or root.is_symlink()
        or not root.is_dir()
        or src.path.is_symlink()
        or not src.path.is_file()
        or not src.path.is_absolute()
        or root.resolve() not in src.path.resolve().parents
        or src.path.name != src.original_sha256 + (
            ".zip" if src.platform == "eis" else ".html"
        )
    ):
        raise WorkerGateError("original owner-private path or identity invalid")
    current = src.path.parent
    while current != root:
        if current.is_symlink():
            raise WorkerGateError("original ancestor symlink forbidden")
        current = current.parent
        if current == current.parent:
            raise WorkerGateError("original root mismatch")
    if stat.S_IMODE(src.path.stat().st_mode) != 0o600:
        raise WorkerGateError("original must be owner-private 0600")
    if not 0 < src.path.stat().st_size <= 8_000_000:
        raise WorkerGateError("original too large or empty")
    h = hashlib.sha256()
    with src.path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    if h.hexdigest() != src.original_sha256:
        raise WorkerGateError("source original SHA mismatch")


def completed_source_versions(session: Session) -> set[str]:
    """Never trust a free-form manual event without its real stored run."""
    source_versions = {src.observation_id: src for src in source_rows(session)}
    rows = session.scalars(
        select(ProcurementLearningObservation).where(
            ProcurementLearningObservation.event_kind == "manual_review",
            ProcurementLearningObservation.visibility_scope == "owner_internal",
            ProcurementLearningObservation.source_ref.startswith(COMPLETION_PREFIX),
        )
    ).all()
    verified = set()
    for item in rows:
        payload = item.payload_json
        if item.training_status != "candidate_unreviewed" or not isinstance(payload, dict):
            continue
        src = source_versions.get(payload.get("source_observation_id"))
        if (
            src is None
            or payload.get("actual_llm_run_verified") is not True
            or payload.get("source_original_sha256") != src.original_sha256
            or item.procurement_ref != src.procurement_ref
        ):
            continue
        run_id = payload.get("run_id")
        if not isinstance(run_id, str):
            continue
        run = session.get(TenderAnalysisRun, run_id)
        if (
            run is None or run.registry_number != src.procurement_ref
            or run.source != "source_queue" or run.status != "completed"
            or run.used_llm is not True or run.sources_count < 1
            or run.llm_model != payload.get("model_label")
        ):
            continue
        report = Path(run.report_path) if run.report_path else None
        if (
            report is None or report.is_symlink() or not report.is_file()
            or not SHA.fullmatch(payload.get("report_sha256") or "")
            or not report.resolve().is_relative_to(
                (Path(load_config().data_dir) / "rag" / "reports").resolve()
            ) or not 0 < report.stat().st_size <= MAX_REPORT
            or hashlib.sha256(report.read_bytes()).hexdigest()
            != payload["report_sha256"]
        ):
            continue
        verified.add(src.observation_id)
    return verified


def check_llm_endpoint(config) -> str:
    endpoint = str(config.local_llm_base_url).rstrip("/")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in {"/v1", "/v1/"}
        or not 1 <= (parsed.port or 80) <= 65535
    ):
        raise WorkerGateError("only configured local loopback LLM endpoint permitted")
    url = endpoint + "/models"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status != 200:
                raise WorkerGateError("local LLM models endpoint not HTTP200")
            raw = response.read(65537)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WorkerGateError("local LLM endpoint unavailable") from exc
    if len(raw) > 65536:
        raise WorkerGateError("LLM models inventory oversized")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WorkerGateError("invalid local LLM model inventory") from exc
    models = data.get("data") if isinstance(data, dict) else None
    choices = {
        row["id"] for row in models
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    } if isinstance(models, list) else set()
    if config.local_llm_model not in choices:
        raise WorkerGateError("configured local LLM model not currently available")
    return config.local_llm_model


def readiness(session: Session, src: PinnedSource, *, root: Path = OWNER_PRIVATE,
              require_services: bool = False, platform_builder=build_data_platform_client,
              llm_checker=check_llm_endpoint,
              llm_base_url: str | None = None,
              llm_model: str | None = None) -> dict:
    result = {
        "ref": src.procurement_ref,
        "source_observation_id": src.observation_id,
        "original_sha256": src.original_sha256,
        "status": "blocked",
        "blockers": [],
        "ready_for_actual_llm": False,
    }
    try:
        attest_source(src, root=root)
    except WorkerGateError:
        result["blockers"].append("source_private_sha_or_access_not_verified")
        return result
    if src.platform != "eis" or not NUMBER.fullmatch(src.procurement_ref):
        result["blockers"].append("marketplace_html_only_no_prepared_tender_documents")
        return result
    repo = TenderRepository(session)
    tender = repo.get_tender_by_registry_number(src.procurement_ref)
    if tender is None:
        result["blockers"].append("eis_tender_not_ingested_into_tender_research")
        return result
    if tender.law_type != "44fz":
        result["blockers"].append("source_regime_requires_independent_preparation")
        return result
    # An indexed tender with the same 19-digit number is NOT proof that its
    # index was built from the precise archived original we are reviewing.
    # Until a prepared-source manifest binds that archive SHA, fail closed.
    payload = tender.raw_payload
    source_bound_sha = (
        payload.get("owner_attested_original_archive_sha256")
        if isinstance(payload, dict) else None
    )
    if source_bound_sha != src.original_sha256:
        result["blockers"].append("indexed_tender_not_bound_to_source_archive_sha")
        return result
    chunks = repo.count_chunks_by_tender(tender.id)
    collection = build_tender_collection_id(repo, tender.id)
    if chunks < 1 or collection is None:
        result["blockers"].append("tender_documents_not_chunked_or_indexed")
        return result
    if require_services:
        config = load_config()
        if llm_base_url is not None:
            object.__setattr__(config, "local_llm_base_url", llm_base_url)
        if llm_model is not None:
            object.__setattr__(config, "local_llm_model", llm_model)
        client = None
        try:
            client = platform_builder(config)
            stats = client.collection_stats(collection)
            if not (
                int(stats.get("resources", -1)) == chunks
                and int(stats.get("embeddings", -1)) >= chunks
            ):
                result["blockers"].append("data_platform_index_incomplete")
        except Exception:  # noqa: BLE001 - do not leak auth/server data
            result["blockers"].append("data_platform_index_unavailable")
        finally:
            if client is not None:
                client.close()
        try:
            llm_checker(config)
        except (WorkerGateError, RuntimeError, ValueError):
            result["blockers"].append("local_llm_model_unavailable")
    else:
        result["blockers"].append("remote_index_and_llm_not_probed_in_dry_run")
    if not result["blockers"]:
        result["status"] = "ready"
        result["ready_for_actual_llm"] = True
    return result


def _real_success(result: TenderAnalysisResult) -> bool:
    return bool(
        result.status == "completed"
        and result.used_llm is True
        and result.sources_count > 0
        and result.llm_calls_count > 0
        and result.report_path
        and result.run_id
        and result.sections
        and all(section.status == "completed" and section.sources
                for section in result.sections)
        and not result.errors
    )


def append_source_link(session: Session, src: PinnedSource,
                       run: TenderAnalysisRun, report_sha256: str) -> bool:
    if (
        run.status != "completed" or not run.used_llm or run.sources_count <= 0
        or run.registry_number != src.procurement_ref or run.source != "source_queue"
        or not SHA.fullmatch(report_sha256)
        or not run.llm_model
    ):
        raise WorkerGateError("not a verified saved actual LLM run")
    event = {
        "event_id": "ta-ready-analysis:" + src.observation_id[:32] + ":" + str(run.id),
        "procurement_ref": src.procurement_ref,
        "event_type": "source_sha_bound_actual_tender_agent_analysis",
        "participation": "reviewed_only",
        "review_state": "system_recorded",
        "source_role": "development_exposed",
        "source_observation_id": src.observation_id,
        "source_original_sha256": src.original_sha256,
        "run_id": str(run.id),
        "report_sha256": report_sha256,
        "model_label": run.llm_model,
        "sources_count": run.sources_count,
        "used_llm": True,
        "actual_llm_run_verified": True,
        "independent_chatgpt_review_performed": False,
        "human_verified_interpretation": False,
        "training_labels": "NOT_REVIEWED",
        "owner_bid_go": False,
        "raw_source_or_report_copied": False,
    }
    return append_candidate(session, make_manual_candidate(event))


def analyse_one(session: Session, src: PinnedSource, *,
                root: Path = OWNER_PRIVATE,
                analyzer=analyze_tender, checker=readiness,
                llm_base_url: str | None = None,
                llm_model: str | None = None) -> dict:
    """Real analyzer, never synthetic success. Caller already backed up DB."""
    att = checker(
        session, src, root=root, require_services=True,
        llm_base_url=llm_base_url, llm_model=llm_model,
    )
    if not att["ready_for_actual_llm"]:
        return {"status": "blocked", "ref": src.procurement_ref,
                "blockers": att["blockers"]}
    before_ids = set(session.scalars(
        select(TenderAnalysisRun.id).where(
            TenderAnalysisRun.registry_number == src.procurement_ref
        )
    ).all())
    result = analyzer(
        src.procurement_ref, session=session, use_llm=True,
        save_report=True, record_history=True, history_source="source_queue",
        analysis_mode="detailed", llm_timeout_seconds=420,
        llm_base_url=llm_base_url, llm_model=llm_model,
    )
    if not _real_success(result):
        return {
            "status": "run_incomplete_not_learning_gold",
            "ref": src.procurement_ref,
            "report_saved_by_analyzer": bool(result.run_id),
            "llm_verified": False,
        }
    run = session.get(TenderAnalysisRun, result.run_id)
    if (
        run is None or run.id in before_ids
        or run.status != "completed" or run.used_llm is not True
        or run.source != "source_queue" or run.registry_number != src.procurement_ref
    ):
        raise WorkerGateError("result not backed by a new persisted actual run")
    # Analysis service writes the report to an existing private data/rag/reports
    # directory. Never reproduce its content in the learning table.
    report = Path(result.report_path)
    expected_dir = (Path(load_config().data_dir) / "rag" / "reports").resolve()
    if (
        report.is_symlink() or not report.is_file()
        or not report.resolve().is_relative_to(expected_dir)
        or not 0 < report.stat().st_size <= MAX_REPORT
    ):
        raise WorkerGateError("real saved report outside approved RAG output")
    # Analysis service normally saves reports with process-default umask;
    # make this new owner-owned standalone report 0600 before linking it in
    # learning metadata. Never change old reports or reveal report text.
    report.chmod(0o600)
    if stat.S_IMODE(report.stat().st_mode) != 0o600:
        raise WorkerGateError("real LLM report privacy gate failed")
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest()
    try:
        inserted = append_source_link(session, src, run, report_sha)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {
        "status": "real_llm_analysis_persisted_and_source_sha_bound",
        "ref": src.procurement_ref,
        "run_id": str(run.id),
        "source_observation_id": src.observation_id,
        "completion_new": inserted,
        "human_gold": False,
        "owner_bid_go": False,
    }


def work_cycle(session: Session, *, root: Path = OWNER_PRIVATE, apply: bool = False,
               max_actual: int = 1, probe_services: bool = False,
               checker=readiness, analyzer=analyze_tender,
               llm_base_url: str | None = None,
               llm_model: str | None = None) -> dict:
    if type(max_actual) is not int or not 1 <= max_actual <= 2:
        raise WorkerGateError("one or two real LLM runs max per cycle")
    if bool(llm_base_url) != bool(llm_model):
        raise WorkerGateError("LLM model and local endpoint must be specified together")
    if llm_base_url:
        parsed = urlsplit(llm_base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.path not in {"/v1", "/v1/"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not isinstance(llm_model, str) or not 1 <= len(llm_model) <= 120
        ):
            raise WorkerGateError("LLM override must be local OpenAI-compatible endpoint")
    sources = source_rows(session)
    done = completed_source_versions(session)
    pending = [s for s in sources if s.observation_id not in done]
    reported = [checker(
        session, src, root=root, require_services=apply or probe_services,
        llm_base_url=llm_base_url, llm_model=llm_model,
    ) for src in pending]
    actual = []
    if apply:
        ready_by_ref = {r["source_observation_id"]: r for r in reported
                        if r["ready_for_actual_llm"] is True}
        for src in pending:
            if len(actual) >= max_actual:
                break
            if src.observation_id not in ready_by_ref:
                continue
            actual.append(analyse_one(
                session, src, root=root, analyzer=analyzer, checker=checker,
                llm_base_url=llm_base_url, llm_model=llm_model,
            ))
    return {
        "schema": "tender_agent_source_analysis_worker_v1",
        "mode": "explicit_actual_llm_apply" if apply else "source_queue_readonly_preflight",
        "pending_source_versions": len(pending),
        "ready_actual_llm_count": sum(r["ready_for_actual_llm"] for r in reported),
        "blocked_source_versions": sum(r["status"] == "blocked" for r in reported),
        "readiness": reported,
        "attempts": actual,
        "genuine_completed_analyses": sum(
            r["status"] == "real_llm_analysis_persisted_and_source_sha_bound"
            for r in actual
        ),
        "blind_gold_promotion": 0,
        "owner_bid_go": 0,
        "independent_chatgpt_comparison": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    parser.add_argument("--max-actual", type=int, default=1)
    parser.add_argument("--probe-services", action="store_true",
                        help="Read-only check actual Data Platform + local model readiness")
    parser.add_argument(
        "--llm-base-url", default=QUALITY_GEMMA_LLAMA_BASE_URL,
        help="Quality default: live llama.cpp Gemma server 127.0.0.1:8081/v1",
    )
    parser.add_argument(
        "--llm-model", default=QUALITY_GEMMA_LLAMA_MODEL,
        help="Quality default: arvectum-gemma4-12b-it-qat-q4_0",
    )
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("explicit canonical database authorization required")
    # Same fcntl lock as source discovery; analysis cannot race source snapshots.
    with single_runner():
        db = create_engine(_engine_url())
        try:
            if args.apply:
                fresh_pg_backup()
            with Session(db) as session:
                report = work_cycle(
                    session, apply=args.apply, max_actual=args.max_actual,
                    probe_services=args.probe_services,
                    llm_base_url=args.llm_base_url, llm_model=args.llm_model
                )
                session.rollback()
        finally:
            db.dispose()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not args.apply or report["genuine_completed_analyses"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
