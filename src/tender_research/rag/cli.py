from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

_load_dotenv_result = load_dotenv(".env", override=False)
_load_dotenv_local_result = load_dotenv(".env.local", override=False)

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.config import load_config
from src.tender_research.rag.analysis_service import analyze_tender
from src.tender_research.rag.data_platform import (
    DataPlatformRagRetriever,
    build_data_platform_client,
    retrieval_backend_name,
)
from src.tender_research.rag.history_service import (
    get_analysis_run,
    get_analysis_run_report,
    list_analysis_runs,
)
from src.tender_research.rag.llm import (
    LocalChatLlmClient,
    SourceCitation,
    build_source_citations,
)
from src.tender_research.rag.schemas import DEFAULT_ANALYSIS_MODE
from src.tender_research.repository import TenderRepository

_RUNTIME_ARGS: argparse.Namespace | None = None
_DEFAULT_HASH_PROVIDER_NAMES = {"hash", "hashing", "local_hash"}






def _get_session() -> Session:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine)()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "default"


def _apply_runtime_overrides(config, args: argparse.Namespace | None) -> None:
    if not args:
        return
    if getattr(args, "llm_base_url", None):
        object.__setattr__(config, "local_llm_base_url", args.llm_base_url)
    if getattr(args, "llm_model", None):
        object.__setattr__(config, "local_llm_model", args.llm_model)
    if getattr(args, "llm_timeout_seconds", None):
        object.__setattr__(config, "local_llm_timeout_seconds", args.llm_timeout_seconds)


def _build_runtime(*, retrieval_only: bool = False):
    session = _get_session()
    repo = TenderRepository(session)
    config = load_config()
    _apply_runtime_overrides(config, _RUNTIME_ARGS)
    retrieval_backend_name(config)
    retriever = DataPlatformRagRetriever(repo, build_data_platform_client(config))
    return session, repo, config, None, None, retriever


def _close_retriever(retriever) -> None:
    close = getattr(retriever, "close", None)
    if close is not None:
        close()


def _add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default=None, help="Deprecated; embeddings are managed by Data Platform")
    parser.add_argument("--model", default=None, help="Deprecated; embeddings are managed by Data Platform")
    parser.add_argument("--base-url", default=None, help="Deprecated; embeddings are managed by Data Platform")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Deprecated; embeddings are managed by Data Platform")
    parser.add_argument("--batch-size", type=int, default=None, help="Deprecated; embeddings are managed by Data Platform")


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--llm-base-url", default=None, help="Local chat LLM base URL override")
    parser.add_argument("--llm-model", default=None, help="Local chat LLM model override")
    parser.add_argument("--llm-timeout-seconds", type=int, default=None, help="Local chat LLM timeout override")


def cmd_build_chunks(args: argparse.Namespace) -> None:
    print("build-chunks is deprecated: document chunking is managed by Data Platform. Run tender preparation instead.")


def cmd_build_embeddings(args: argparse.Namespace) -> None:
    print("build-embeddings is deprecated: embeddings are managed by Data Platform. Run tender preparation instead.")


def cmd_search(args: argparse.Namespace) -> None:
    session, _repo, config, _provider, _vector_store, retriever = _build_runtime(
        retrieval_only=True
    )
    retrieval_backend_name(config)
    if args.tender_id or args.registry_number:
        hits = retriever.search_documents(
            args.query,
            tender_id=args.tender_id,
            registry_number=args.registry_number,
            customer_name=args.customer_name,
            limit=args.limit,
        )
    else:
        hits = retriever.search_all_documents(args.query, limit=args.limit)
    retrieval_provider = "data_platform"
    retrieval_model = "hybrid"
    print(f"provider: {retrieval_provider}")
    print(f"model: {retrieval_model}")
    print(f"hits: {len(hits)}")
    for hit in hits:
        print(f"score: {hit.score:.4f}")
        print(f"chunk_id: {hit.chunk_id}")
        print(f"registry_number: {hit.registry_number}")
        print(f"tender_id: {hit.tender_id}")
        print(f"tender_title: {hit.tender_title}")
        print(f"customer: {hit.customer_name}")
        print(f"document: {hit.file_name}")
        print(f"preview: {hit.preview}")
        print()
    _close_retriever(retriever)
    session.close()


def cmd_ask(args: argparse.Namespace) -> None:
    session, _repo, config, _provider, _vector_store, retriever = _build_runtime(
        retrieval_only=True
    )
    hits = retriever.search_documents(
        args.question,
        registry_number=args.registry_number,
        limit=args.limit,
    )
    llm_enabled = bool(args.use_llm or config.rag_use_llm)
    sources = build_source_citations(hits)

    print(f"registry_number: {args.registry_number}")
    print(f"question: {args.question}")
    retrieval_backend_name(config)
    print("retrieval_provider: data_platform")
    print("retrieval_model: hybrid")
    print(f"context_hits: {len(hits)}")
    if llm_enabled:
        print(f"llm_model: {config.local_llm_model}")
        print(f"llm_base_url: {config.local_llm_base_url}")

    if not hits:
        print("answer_mode: retrieval_only")
        print("answer:")
        print("Контекст не найден в локальном индексе.")
        print("sources: 0")
        _close_retriever(retriever)
        session.close()
        return

    if llm_enabled:
        answer = _build_local_llm_client(config).generate_answer(
            args.question,
            hits,
            registry_number=args.registry_number,
        )
        if answer.error:
            print("answer_mode: retrieval_fallback")
            print(f"llm_error: {answer.error}")
            print("answer:")
            print("LLM недоступна или не вернула корректный ответ. Ниже релевантные фрагменты.")
            _print_sources(answer.sources or sources)
        else:
            print("answer_mode: local_llm")
            print("answer:")
            print(answer.answer)
            _print_sources(answer.sources)
    else:
        print("answer_mode: retrieval_only")
        print("answer:")
        print("LLM не использовалась. Ниже релевантные фрагменты.")
        _print_sources(sources)
    _close_retriever(retriever)
    session.close()


def cmd_analyze_tender(args: argparse.Namespace) -> None:
    result = analyze_tender(
        args.registry_number,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        batch_size=args.batch_size,
        use_llm=bool(args.use_llm),
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
        llm_timeout_seconds=args.llm_timeout_seconds,
        limit=args.limit,
        analysis_mode=args.analysis_mode,
        max_context_chars_per_section=args.max_context_chars_per_section,
        max_chunks_per_section=args.max_chunks_per_section,
        save_report=True,
        record_history=not getattr(args, "no_history", False),
        history_source="cli",
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.report_markdown or "", encoding="utf-8")
        print(f"output_path: {output_path}")
    else:
        print(json.dumps({
            "status": result.status,
            "registry_number": result.registry_number,
            "sections_count": result.sections_count,
            "sources_count": result.sources_count,
            "ri223_source_observations": result.ri223_source_observations,
            "ri223_review_flags": result.ri223_review_flags,
            "ri223_document_dossier": result.ri223_document_dossier,
            "analysis_mode": result.analysis_mode,
            "used_llm": result.used_llm,
            "llm_model": result.llm_model,
            "llm_endpoint": result.llm_endpoint,
            "retrieval_provider": result.retrieval_provider,
            "retrieval_model": result.retrieval_model,
            "retrieval_limit_used": result.retrieval_limit_used,
            "duration_seconds": result.duration_seconds,
            "timings": result.timings,
            "per_section_timings": result.per_section_timings,
            "llm_calls_count": result.llm_calls_count,
            "total_context_chars": result.total_context_chars,
            "max_section_context_chars": result.max_section_context_chars,
            "avg_section_llm_seconds": result.avg_section_llm_seconds,
            "report_path": result.report_path,
            "warnings": result.warnings,
            "errors": result.errors,
        }, ensure_ascii=False, indent=2))
        print()
        print(result.report_markdown)



def _build_local_llm_client(config) -> LocalChatLlmClient:
    return LocalChatLlmClient(
        base_url=config.local_llm_base_url,
        model_name=config.local_llm_model,
        timeout_seconds=int(config.local_llm_timeout_seconds or 120),
    )


def _print_sources(sources: list[SourceCitation]) -> None:
    print(f"sources: {len(sources)}")
    for index, source in enumerate(sources, start=1):
        print(f"[source {index}]")
        print(f"registry_number: {source.registry_number}")
        print(f"tender_title: {source.tender_title}")
        print(f"customer: {source.customer_name}")
        print(f"document_file_name: {source.document_file_name}")
        print(f"document_id: {source.document_id}")
        print(f"chunk_id: {source.chunk_id}")
        print(f"score: {source.score:.4f}")
        print(f"preview: {source.quote_preview}")
        print()


def cmd_check_embedding_server(args: argparse.Namespace) -> None:
    print("check-embedding-server is deprecated: embedding health belongs to Data Platform.")


def cmd_eval(args: argparse.Namespace) -> None:
    session, _repo, config, _provider, _vector_store, retriever = _build_runtime(
        retrieval_only=True
    )
    retrieval_backend_name(config)
    retrieval_provider = "data_platform"
    retrieval_model = "hybrid"
    questions_path = Path(args.questions)
    questions = json.loads(questions_path.read_text(encoding="utf-8"))

    eval_dir = Path(config.data_dir) / "rag" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    output_path = eval_dir / (
        f"{_slugify(retrieval_provider)}__{_slugify(retrieval_model)}__"
        f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    )

    questions_with_results = 0
    empty_results = 0
    top_scores: list[float] = []
    top_documents: Counter[str] = Counter()

    with output_path.open("w", encoding="utf-8") as handle:
        for item in questions:
            # Offline retrieval evaluation intentionally measures the entire
            # index. It is an administrative command, not procurement
            # analysis, so it must use the explicit unscoped API.
            hits = retriever.search_all_documents(item["query"], limit=args.limit)
            if hits:
                questions_with_results += 1
                top_scores.append(hits[0].score)
                top_documents[hits[0].file_name] += 1
            else:
                empty_results += 1
            row = {
                "id": item["id"],
                "query": item["query"],
                "category": item.get("category"),
                "provider": retrieval_provider,
                "model": retrieval_model,
                "results": [
                    {
                        "score": hit.score,
                        "registry_number": hit.registry_number,
                        "tender_id": hit.tender_id,
                        "tender_title": hit.tender_title,
                        "customer_name": hit.customer_name,
                        "document": hit.file_name,
                        "chunk_id": hit.chunk_id,
                        "preview": hit.preview,
                    }
                    for hit in hits
                ],
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "questions_total": len(questions),
        "questions_with_results": questions_with_results,
        "empty_results": empty_results,
        "avg_top_score": round(sum(top_scores) / len(top_scores), 4) if top_scores else 0.0,
        "top_documents": top_documents.most_common(5),
        "provider": retrieval_provider,
        "model": retrieval_model,
        "output_path": str(output_path),
    }
    for key in (
        "questions_total",
        "questions_with_results",
        "empty_results",
        "avg_top_score",
        "top_documents",
        "provider",
        "model",
        "output_path",
    ):
        print(f"{key}: {summary[key]}")
    session.close()

def _get_session() -> Session:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=engine)()


def cmd_list_analysis_runs(args: argparse.Namespace) -> None:
    session = _get_session()
    try:
        items, total = list_analysis_runs(
            session,
            registry_number=args.registry_number,
            status=args.status,
            limit=args.limit,
            offset=args.offset,
        )
        data = [r.to_dict() for r in items]
        print(json.dumps({"items": data, "limit": args.limit, "offset": args.offset, "total": total}, ensure_ascii=False, indent=2))
    finally:
        session.close()


def cmd_show_analysis_run(args: argparse.Namespace) -> None:
    session = _get_session()
    try:
        record = get_analysis_run(session, args.run_id)
        if record is None:
            print(json.dumps({"error": "Analysis run not found"}, indent=2))
            return
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    finally:
        session.close()


def cmd_show_analysis_report(args: argparse.Namespace) -> None:
    config = load_config()
    session = _get_session()
    try:
        record, markdown, error = get_analysis_run_report(session, args.run_id, config.data_dir)
        if record is None:
            print(json.dumps({"error": error or "Analysis run not found"}, indent=2))
            return
        if markdown is None:
            print(json.dumps({"error": error or "Report file is missing", "run_id": args.run_id}, indent=2))
            return
        print(markdown)
    finally:
        session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tender Research CLI backed by Arvectum Data Platform")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chunks = sub.add_parser("build-chunks", help="Deprecated: chunking is managed by Data Platform")
    p_chunks.add_argument("--limit", type=int, default=100)

    p_embeddings = sub.add_parser("build-embeddings", help="Deprecated: embeddings are managed by Data Platform")
    p_embeddings.add_argument("--limit", type=int, default=1000)
    _add_provider_args(p_embeddings)

    p_search = sub.add_parser("search", help="Search indexed document chunks")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--tender-id", default=None)
    p_search.add_argument("--registry-number", default=None)
    p_search.add_argument("--customer-name", default=None)
    _add_provider_args(p_search)

    p_ask = sub.add_parser("ask", help="Ask a question against one registry number")
    p_ask.add_argument("--registry-number", required=True)
    p_ask.add_argument("--question", required=True)
    p_ask.add_argument("--limit", type=int, default=6)
    p_ask.add_argument("--use-llm", action="store_true")
    _add_provider_args(p_ask)
    _add_llm_args(p_ask)

    p_analyze = sub.add_parser("analyze-tender", help="Build a structured RAG analysis report for one registry number")
    p_analyze.add_argument("--registry-number", required=True)
    p_analyze.add_argument("--limit", type=int, default=None)
    p_analyze.add_argument("--use-llm", action="store_true")
    p_analyze.add_argument(
        "--analysis-mode",
        choices=["fast", "balanced", "detailed"],
        default=DEFAULT_ANALYSIS_MODE,
        help="Latency/detail preset for tender analysis",
    )
    p_analyze.add_argument("--max-context-chars-per-section", type=int, default=None)
    p_analyze.add_argument("--max-chunks-per-section", type=int, default=None)
    p_analyze.add_argument("--output", default=None, help="Optional markdown output path")
    p_analyze.add_argument("--no-history", action="store_true", help="Skip saving to analysis history")
    _add_provider_args(p_analyze)
    _add_llm_args(p_analyze)

    p_history_list = sub.add_parser("list-analysis-runs", help="List analysis history runs")
    p_history_list.add_argument("--registry-number", default=None)
    p_history_list.add_argument("--status", default=None)
    p_history_list.add_argument("--limit", type=int, default=20)
    p_history_list.add_argument("--offset", type=int, default=0)

    p_history_show = sub.add_parser("show-analysis-run", help="Show details of a specific analysis run")
    p_history_show.add_argument("--run-id", required=True)

    p_history_report = sub.add_parser("show-analysis-report", help="Show report markdown for a specific analysis run")
    p_history_report.add_argument("--run-id", required=True)

    p_check = sub.add_parser("check-embedding-server", help="Deprecated: check Data Platform /health instead")
    _add_provider_args(p_check)

    p_eval = sub.add_parser("eval", help="Run retrieval eval on a set of procurement questions")
    p_eval.add_argument("--questions", required=True, help="Path to evaluation questions JSON")
    p_eval.add_argument("--limit", type=int, default=5, help="Top-k results per question")
    _add_provider_args(p_eval)

    return parser


def main() -> None:
    global _RUNTIME_ARGS
    parser = build_parser()
    args = parser.parse_args()
    _RUNTIME_ARGS = args
    try:
        if args.command == "build-chunks":
            cmd_build_chunks(args)
        elif args.command == "build-embeddings":
            cmd_build_embeddings(args)
        elif args.command == "check-embedding-server":
            cmd_check_embedding_server(args)
        elif args.command == "eval":
            cmd_eval(args)
        elif args.command == "search":
            cmd_search(args)
        elif args.command == "ask":
            cmd_ask(args)
        elif args.command == "analyze-tender":
            cmd_analyze_tender(args)
        elif args.command == "list-analysis-runs":
            cmd_list_analysis_runs(args)
        elif args.command == "show-analysis-run":
            cmd_show_analysis_run(args)
        elif args.command == "show-analysis-report":
            cmd_show_analysis_report(args)
    finally:
        _RUNTIME_ARGS = None


if __name__ == "__main__":
    main()
