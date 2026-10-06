from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.config import load_config
from src.tender_research.rag.data_platform import (
    DataPlatformError,
    DataPlatformRagRetriever,
    build_data_platform_client,
    build_tender_collection_id,
    retrieval_backend_name,
)
from src.tender_research.rag.history_service import record_analysis_run
from src.tender_research.rag.llm import (
    LocalChatLlmClient,
    build_source_citations,
)
from src.tender_research.rag.schemas import (
    ANALYSIS_MODE_CHOICES,
    ANALYSIS_SECTIONS,
    DEFAULT_ANALYSIS_MODE,
    SourceCitation,
    TenderAnalysisResult,
    TenderAnalysisSection,
)
from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisModeConfig:
    name: str
    retrieval_limit: int
    max_chunks_per_section: int
    max_context_chars_per_section: int
    max_chunk_chars: int
    max_preview_chars_per_source: int
    llm_timeout_seconds: int


@dataclass(frozen=True)
class SectionContext:
    hits: list[RagSearchHit]
    chunks_considered: int
    chunks_used: int
    context_chars: int
    truncated_chunks: int


_ANALYSIS_MODE_PRESETS: dict[str, AnalysisModeConfig] = {
    "fast": AnalysisModeConfig(
        name="fast",
        retrieval_limit=3,
        max_chunks_per_section=3,
        max_context_chars_per_section=4_000,
        max_chunk_chars=1_200,
        max_preview_chars_per_source=500,
        llm_timeout_seconds=90,
    ),
    "balanced": AnalysisModeConfig(
        name="balanced",
        retrieval_limit=5,
        max_chunks_per_section=5,
        max_context_chars_per_section=7_000,
        max_chunk_chars=1_800,
        max_preview_chars_per_source=800,
        llm_timeout_seconds=180,
    ),
    "detailed": AnalysisModeConfig(
        name="detailed",
        retrieval_limit=8,
        max_chunks_per_section=8,
        max_context_chars_per_section=12_000,
        max_chunk_chars=2_500,
        max_preview_chars_per_source=1_200,
        llm_timeout_seconds=300,
    ),
}


def _slugify(value: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "default"



def _normalize_analysis_mode(analysis_mode: str | None) -> str:
    normalized = str(analysis_mode or DEFAULT_ANALYSIS_MODE).strip().lower()
    if normalized not in ANALYSIS_MODE_CHOICES:
        return DEFAULT_ANALYSIS_MODE
    return normalized


def _resolve_analysis_mode_config(
    *,
    analysis_mode: str | None,
    limit: int | None,
    max_context_chars_per_section: int | None,
    max_chunks_per_section: int | None,
    llm_timeout_seconds: int | None,
) -> AnalysisModeConfig:
    normalized_mode = _normalize_analysis_mode(analysis_mode)
    preset = _ANALYSIS_MODE_PRESETS[normalized_mode]
    return AnalysisModeConfig(
        name=normalized_mode,
        retrieval_limit=max(1, int(limit or preset.retrieval_limit)),
        max_chunks_per_section=max(1, int(max_chunks_per_section or preset.max_chunks_per_section)),
        max_context_chars_per_section=max(500, int(max_context_chars_per_section or preset.max_context_chars_per_section)),
        max_chunk_chars=preset.max_chunk_chars,
        max_preview_chars_per_source=preset.max_preview_chars_per_source,
        llm_timeout_seconds=max(1, int(llm_timeout_seconds or preset.llm_timeout_seconds)),
    )


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    trimmed = text[: limit - 3].rsplit(" ", 1)[0].strip()
    return (trimmed or text[: limit - 3].strip()) + "..."


def _estimate_tokens(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, round(chars / 4))


def build_section_context(
    hits: list[RagSearchHit],
    *,
    max_chunks: int,
    max_context_chars: int,
    max_chunk_chars: int,
    max_preview_chars: int,
) -> SectionContext:
    selected: list[RagSearchHit] = []
    context_chars = 0
    truncated_chunks = 0
    for hit in hits[:max_chunks]:
        remaining_chars = max_context_chars - context_chars
        if remaining_chars <= 0:
            break

        trimmed_text = _trim_text(hit.text, min(max_chunk_chars, remaining_chars))
        if not trimmed_text:
            continue
        if len(trimmed_text) < len((hit.text or "").strip()):
            truncated_chunks += 1

        if len(trimmed_text) > remaining_chars:
            trimmed_text = _trim_text(trimmed_text, remaining_chars)
            if not trimmed_text:
                continue
            truncated_chunks += 1

        trimmed_preview = _trim_text(hit.preview, max_preview_chars)
        selected.append(replace(hit, text=trimmed_text, preview=trimmed_preview))
        context_chars += len(trimmed_text)

    return SectionContext(
        hits=selected,
        chunks_considered=min(len(hits), max_chunks),
        chunks_used=len(selected),
        context_chars=context_chars,
        truncated_chunks=truncated_chunks,
    )


def _build_history_metadata(result: TenderAnalysisResult) -> dict:
    return {
        "analysis_mode": result.analysis_mode,
        "duration_seconds": result.duration_seconds,
        "timings": result.timings,
        "per_section_timings": result.per_section_timings,
        "llm_calls_count": result.llm_calls_count,
        "total_context_chars": result.total_context_chars,
        "max_section_context_chars": result.max_section_context_chars,
        "avg_section_llm_seconds": result.avg_section_llm_seconds,
        "llm_endpoint": result.llm_endpoint,
        "retrieval_limit_used": result.retrieval_limit_used,
    }


def _get_session() -> Session:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=engine)()


def _build_report_markdown(
    registry_number: str,
    sections: list[TenderAnalysisSection],
    used_llm: bool,
    llm_model: str | None,
    retrieval_provider: str | None,
    retrieval_model: str | None,
    analysis_mode: str = DEFAULT_ANALYSIS_MODE,
    duration_seconds: float | None = None,
) -> str:
    lines = [
        f"# Анализ закупки {registry_number}",
        "",
        "**Статус:** завершено",
        f"**Режим анализа:** {analysis_mode}",
        f"**LLM:** {'да' if used_llm else 'нет'} {f'({llm_model})' if llm_model and used_llm else ''}",
        f"**Поиск:** {retrieval_provider or '?'} / {retrieval_model or '?'}",
        f"**Разделов:** {len(sections)}",
        f"**Источников:** {sum(len(s.sources) for s in sections)}",
        "",
    ]
    if duration_seconds is not None:
        lines.append(f"**Длительность:** {duration_seconds:.2f} сек")
    lines.extend(["", "---", ""])
    for section in sections:
        lines.append(f"## {section.id}. {section.title}")
        lines.append("")
        if section.status == "insufficient_context":
            lines.append("*Недостаточно контекста в документах для ответа.*")
            lines.append("")
            continue
        if section.status == "no_context":
            lines.append("*Нет документов для анализа.*")
            lines.append("")
            continue
        lines.append(section.answer)
        lines.append("")
        if section.sources:
            lines.append("**Источники:**")
            lines.append("")
            for idx, src in enumerate(section.sources, start=1):
                lines.append(f"{idx}. **{src.document_file_name}**")
                lines.append(f"   - chunk_id: `{src.chunk_id}`")
                lines.append(f"   - registry_number: {src.registry_number or '-'}")
                lines.append(f"   - tender_title: {src.tender_title}")
                lines.append(f"   - score: {src.score:.4f}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _save_report(report_markdown: str, registry_number: str, data_dir: str, *, run_token: str | None = None) -> str:
    reports_dir = Path(data_dir) / "rag" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if run_token is None:
        from datetime import datetime

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        run_token = f"{timestamp}_{uuid4().hex[:8]}"
    output_path = reports_dir / f"analyze_tender_{registry_number}_{run_token}.md"
    output_path.write_text(report_markdown, encoding="utf-8")
    return str(output_path)


def _record_history(
    result: TenderAnalysisResult,
    session: Session,
    *,
    duration_seconds: float | None = None,
    source: str | None = None,
) -> str | None:
    try:
        run = record_analysis_run(
            session,
            registry_number=result.registry_number,
            status=result.status,
            used_llm=result.used_llm,
            llm_model=result.llm_model,
            retrieval_provider=result.retrieval_provider,
            retrieval_model=result.retrieval_model,
            sections_count=result.sections_count,
            sources_count=result.sources_count,
            report_path=result.report_path,
            report_markdown=result.report_markdown,
            warnings=result.warnings,
            errors=result.errors,
            duration_seconds=duration_seconds,
            source=source,
            metadata=_build_history_metadata(result),
        )
        return run.id
    except Exception as e:  # noqa: BLE001
        # record_analysis_run() writes through the caller's Session. If its
        # flush/commit fails, SQLAlchemy leaves that Session in failed-
        # transaction state. History is best-effort, so recover the Session
        # before returning the already completed analysis to the orchestrator.
        session.rollback()
        logger.warning("Analysis completed, but history record was not saved: %s", e)
        return None


def _finalize_analysis_status(
    *,
    sections: list[TenderAnalysisSection],
    sources_count: int,
    warnings: list[str],
    errors: list[str],
    use_llm: bool,
) -> tuple[str, list[str]]:
    normalized_warnings = list(warnings)
    if errors:
        return "failed", normalized_warnings
    if sources_count <= 0:
        message = "Analysis completed, but no cited sources were found."
        if message not in normalized_warnings:
            normalized_warnings.append(message)
        return "completed_with_warnings", normalized_warnings
    if normalized_warnings:
        return "completed_with_warnings", normalized_warnings
    if any(section.status in ("insufficient_context", "no_context", "retrieval_only_fallback") for section in sections):
        return "completed_with_warnings", normalized_warnings
    return "completed", normalized_warnings


def analyze_tender(
    registry_number: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: int | None = None,
    batch_size: int | None = None,
    use_llm: bool = False,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    llm_timeout_seconds: int | None = None,
    limit: int | None = None,
    analysis_mode: str = DEFAULT_ANALYSIS_MODE,
    max_context_chars_per_section: int | None = None,
    max_chunks_per_section: int | None = None,
    session: Session | None = None,
    save_report: bool = False,
    record_history: bool = True,
    history_source: str | None = None,
    progress_callback=None,
) -> TenderAnalysisResult:
    own_session = False
    if session is None:
        session = _get_session()
        own_session = True
    platform_client = None

    try:
        warnings: list[str] = []
        errors: list[str] = []
        config = load_config()
        mode_config = _resolve_analysis_mode_config(
            analysis_mode=analysis_mode,
            limit=limit,
            max_context_chars_per_section=max_context_chars_per_section,
            max_chunks_per_section=max_chunks_per_section,
            llm_timeout_seconds=llm_timeout_seconds,
        )
        analysis_mode = mode_config.name
        started_at = time.perf_counter()

        def emit_progress(
            progress_percent: int,
            current_step: str,
            message: str = "",
            *,
            steps: list[dict] | None = None,
            current_section_title: str | None = None,
            current_section_index: int | None = None,
            total_sections: int | None = None,
        ) -> None:
            if progress_callback is None:
                return
            payload = {
                "progress_percent": progress_percent,
                "current_step": current_step,
                "message": message,
            }
            if steps is not None:
                payload["steps"] = steps
            if current_section_title is not None:
                payload["current_section_title"] = current_section_title
            if current_section_index is not None:
                payload["current_section_index"] = current_section_index
            if total_sections is not None:
                payload["total_sections"] = total_sections
            progress_callback(payload)

        if llm_base_url:
            object.__setattr__(config, "local_llm_base_url", llm_base_url)
        if llm_model:
            object.__setattr__(config, "local_llm_model", llm_model)
        object.__setattr__(config, "local_llm_timeout_seconds", mode_config.llm_timeout_seconds)

        repo = TenderRepository(session)
        tender = repo.get_tender_by_registry_number(registry_number)
        if not tender:
            tender = repo.get_tender_by_external("eis", registry_number)
        if not tender:
            tender = repo.get_tender_by_external("external_public_44fz", registry_number)
        if not tender:
            result = TenderAnalysisResult(
                status="no_context",
                registry_number=registry_number,
                sections=[],
                sections_count=0,
                sources_count=0,
                analysis_mode=analysis_mode,
                errors=[f"Tender {registry_number} not found in database"],
            )
            if record_history:
                _record_history(result, session, duration_seconds=0.0, source=history_source)
            return result

        retrieval_backend_name(config)
        emit_progress(10, "retrieval", "Подготавливаем поиск по документам…")

        retrieval_provider = "data_platform"
        retrieval_model = "hybrid"
        platform_client = build_data_platform_client(config)
        collection_id = build_tender_collection_id(repo, tender.id)
        platform_index_ready = False
        if collection_id is not None:
            try:
                stats = platform_client.collection_stats(collection_id)
                expected_resources = repo.count_chunks_by_tender(tender.id)
                platform_index_ready = (
                    expected_resources > 0
                    and int(stats.get("resources", 0)) == expected_resources
                    and int(stats.get("embeddings", 0)) >= expected_resources
                )
            except (DataPlatformError, ValueError):
                platform_index_ready = False
        if collection_id is None or not platform_index_ready:
            result = TenderAnalysisResult(
                status="no_context",
                registry_number=registry_number,
                sections=[],
                sections_count=0,
                sources_count=0,
                analysis_mode=analysis_mode,
                errors=[
                    (
                        "Data Platform index is not prepared for this tender. "
                        "Run tender preparation first."
                    )
                ],
                retrieval_provider=retrieval_provider,
                retrieval_model=retrieval_model,
                retrieval_limit_used=mode_config.retrieval_limit,
            )
            if record_history:
                _record_history(
                    result,
                    session,
                    duration_seconds=0.0,
                    source=history_source,
                )
            return result
        retriever = DataPlatformRagRetriever(repo, platform_client)

        llm_client: LocalChatLlmClient | None = None
        if use_llm:
            try:
                llm_client = LocalChatLlmClient(
                    base_url=config.local_llm_base_url,
                    model_name=config.local_llm_model,
                    timeout_seconds=mode_config.llm_timeout_seconds,
                    max_context_chars=mode_config.max_context_chars_per_section,
                )
            except Exception as e:  # noqa: BLE001
                warnings.append(f"LLM client init failed: {e}")
                use_llm = False

        sections: list[TenderAnalysisSection] = []
        all_sources: list[SourceCitation] = []
        per_section_timings: list[dict] = []
        section_states = [
            {
                "name": f"section:{sec_def['id']}",
                "title": f"{index}/{len(ANALYSIS_SECTIONS)} — {sec_def['title']}",
                "status": "pending",
                "progress_percent": 0,
                "message": "",
                "details": {
                    "section_id": sec_def["id"],
                    "section_title": sec_def["title"],
                    "section_index": index,
                    "total_sections": len(ANALYSIS_SECTIONS),
                },
            }
            for index, sec_def in enumerate(ANALYSIS_SECTIONS, start=1)
        ]
        retrieval_seconds_total = 0.0
        llm_calls_count = 0
        total_context_chars = 0
        max_section_context_chars_value = 0
        llm_durations: list[float] = []

        total_sections = max(len(ANALYSIS_SECTIONS), 1)
        emit_progress(
            20,
            "retrieval",
            "Поиск по документам готов. Начинаем анализ по разделам…",
            steps=section_states,
        )
        for index, sec_def in enumerate(ANALYSIS_SECTIONS, start=1):
            section_started_at = time.perf_counter()
            section_progress = 20 + round((index - 1) * 70 / total_sections)
            section_states[index - 1]["status"] = "running"
            section_states[index - 1]["progress_percent"] = section_progress
            section_states[index - 1]["message"] = "Идёт поиск и сбор контекста."
            emit_progress(
                section_progress,
                "section_analysis",
                f"{index}/{total_sections} — {sec_def['title']}",
                steps=section_states,
                current_section_title=sec_def["title"],
                current_section_index=index,
                total_sections=total_sections,
            )
            retrieval_started_at = time.perf_counter()
            hits = retriever.search_documents(
                sec_def["question"],
                registry_number=registry_number,
                limit=mode_config.retrieval_limit,
            )
            retrieval_seconds = time.perf_counter() - retrieval_started_at
            retrieval_seconds_total += retrieval_seconds
            sources = build_source_citations(hits)
            all_sources.extend(sources)
            section_context = build_section_context(
                hits,
                max_chunks=mode_config.max_chunks_per_section,
                max_context_chars=mode_config.max_context_chars_per_section,
                max_chunk_chars=mode_config.max_chunk_chars,
                max_preview_chars=mode_config.max_preview_chars_per_source,
            )
            total_context_chars += section_context.context_chars
            max_section_context_chars_value = max(max_section_context_chars_value, section_context.context_chars)
            prompt_metrics = {
                "context_chars": section_context.context_chars,
                "context_tokens_estimate": _estimate_tokens(section_context.context_chars),
                "prompt_chars": 0,
                "system_prompt_chars": 0,
                "user_prompt_chars": 0,
            }
            llm_seconds = 0.0
            llm_status = "not_used"
            fallback_reason: str | None = None
            answer_warning: str | None = None

            if not hits:
                section_states[index - 1]["status"] = "warning" if llm_client else "completed"
                section_states[index - 1]["progress_percent"] = 100
                section_states[index - 1]["message"] = "Недостаточно контекста в документах."
                sections.append(TenderAnalysisSection(
                    id=sec_def["id"],
                    title=sec_def["title"],
                    question=sec_def["question"],
                    answer="",
                    sources=[],
                    status="insufficient_context" if llm_client else "no_context",
                ))
                per_section_timings.append(
                    {
                        "section_id": sec_def["id"],
                        "section_title": sec_def["title"],
                        "section_index": index,
                        "status": sections[-1].status,
                        "retrieval_seconds": round(retrieval_seconds, 4),
                        "llm_seconds": 0.0,
                        "duration_seconds": round(time.perf_counter() - section_started_at, 4),
                        "chunks_retrieved": len(hits),
                        "chunks_used": 0,
                        "context_chars": 0,
                        "context_tokens_estimate": 0,
                        "prompt_chars": 0,
                        "system_prompt_chars": 0,
                        "user_prompt_chars": 0,
                        "llm_used": False,
                        "fallback_reason": None,
                    }
                )
                continue

            if use_llm and llm_client:
                prompt_metrics = llm_client.build_prompt_metrics(
                    sec_def["question"],
                    section_context.hits,
                    registry_number=registry_number,
                    analysis_mode=analysis_mode,
                )
                prompt_metrics["context_tokens_estimate"] = _estimate_tokens(section_context.context_chars)
                section_states[index - 1]["message"] = "Выполняем запрос к локальной LLM."
                emit_progress(
                    section_progress,
                    "section_analysis",
                    f"{index}/{total_sections} — {sec_def['title']}",
                    steps=section_states,
                    current_section_title=sec_def["title"],
                    current_section_index=index,
                    total_sections=total_sections,
                )
                llm_started_at = time.perf_counter()
                answer = llm_client.generate_answer(
                    sec_def["question"],
                    section_context.hits,
                    registry_number=registry_number,
                    analysis_mode=analysis_mode,
                )
                llm_seconds = time.perf_counter() - llm_started_at
                llm_calls_count += 1
                llm_durations.append(llm_seconds)
                if answer.error:
                    answer_text = _retrieval_only_answer(hits)
                    status = "retrieval_only_fallback"
                    llm_status = "fallback"
                    fallback_reason = answer.error
                    answer_warning = f"LLM fallback for section {sec_def['id']}: {answer.error}"
                    warnings.append(answer_warning)
                else:
                    answer_text = answer.answer
                    status = "completed"
                    llm_status = "completed"
            else:
                answer_text = _retrieval_only_answer(hits)
                status = "retrieval_only"

            section_duration = time.perf_counter() - section_started_at
            section_states[index - 1]["status"] = "warning" if status == "retrieval_only_fallback" else "completed"
            section_states[index - 1]["progress_percent"] = 100
            section_states[index - 1]["message"] = (
                "Готово с retrieval fallback."
                if status == "retrieval_only_fallback"
                else "Раздел завершён."
            )
            section_states[index - 1]["details"] = {
                **section_states[index - 1]["details"],
                "retrieval_seconds": round(retrieval_seconds, 4),
                "llm_seconds": round(llm_seconds, 4),
                "duration_seconds": round(section_duration, 4),
                "chunks_retrieved": len(hits),
                "chunks_used": section_context.chunks_used,
                "context_chars": section_context.context_chars,
                "context_tokens_estimate": _estimate_tokens(section_context.context_chars),
                "fallback_reason": fallback_reason,
            }
            sections.append(TenderAnalysisSection(
                id=sec_def["id"],
                title=sec_def["title"],
                question=sec_def["question"],
                answer=answer_text,
                sources=sources,
                status=status,
            ))
            per_section_timings.append(
                {
                    "section_id": sec_def["id"],
                    "section_title": sec_def["title"],
                    "section_index": index,
                    "status": status,
                    "retrieval_seconds": round(retrieval_seconds, 4),
                    "llm_seconds": round(llm_seconds, 4),
                    "duration_seconds": round(section_duration, 4),
                    "chunks_retrieved": len(hits),
                    "chunks_used": section_context.chunks_used,
                    "chunks_considered": section_context.chunks_considered,
                    "truncated_chunks": section_context.truncated_chunks,
                    "context_chars": section_context.context_chars,
                    "context_tokens_estimate": _estimate_tokens(section_context.context_chars),
                    "prompt_chars": prompt_metrics.get("prompt_chars", 0),
                    "system_prompt_chars": prompt_metrics.get("system_prompt_chars", 0),
                    "user_prompt_chars": prompt_metrics.get("user_prompt_chars", 0),
                    "llm_used": llm_status == "completed",
                    "llm_call_attempted": use_llm and llm_client is not None,
                    "fallback_reason": fallback_reason,
                    "warning": answer_warning,
                }
            )
            completed_progress = 20 + round(index * 70 / total_sections)
            emit_progress(
                completed_progress,
                "section_analysis",
                f"{index}/{total_sections} — {sec_def['title']} завершён",
                steps=section_states,
                current_section_title=sec_def["title"],
                current_section_index=index,
                total_sections=total_sections,
            )
        emit_progress(90, "section_analysis", "Анализ разделов завершён.", steps=section_states)

        sources_count = len({source.chunk_id for source in all_sources})
        overall_status, warnings = _finalize_analysis_status(
            sections=sections,
            sources_count=sources_count,
            warnings=warnings,
            errors=errors,
            use_llm=use_llm,
        )
        duration = time.perf_counter() - started_at
        avg_section_llm_seconds = round(sum(llm_durations) / len(llm_durations), 4) if llm_durations else None
        slowest_sections = sorted(
            per_section_timings,
            key=lambda item: float(item.get("duration_seconds") or 0.0),
            reverse=True,
        )[:3]
        timings = {
            "total_seconds": round(duration, 4),
            "retrieval_seconds": round(retrieval_seconds_total, 4),
            "llm_seconds": round(sum(llm_durations), 4),
            "slowest_sections": [
                {
                    "section_id": item["section_id"],
                    "section_title": item["section_title"],
                    "duration_seconds": item["duration_seconds"],
                }
                for item in slowest_sections
            ],
            "llm_model": config.local_llm_model if use_llm else None,
            "llm_endpoint": config.local_llm_base_url if use_llm else None,
            "top_k_limit": mode_config.retrieval_limit,
            "max_chunks_per_section": mode_config.max_chunks_per_section,
            "max_context_chars_per_section": mode_config.max_context_chars_per_section,
            "llm_timeout_seconds": mode_config.llm_timeout_seconds,
        }

        report_markdown = _build_report_markdown(
            registry_number=registry_number,
            sections=sections,
            used_llm=use_llm and llm_client is not None,
            llm_model=config.local_llm_model if use_llm else None,
            retrieval_provider=retrieval_provider,
            retrieval_model=retrieval_model,
            analysis_mode=analysis_mode,
            duration_seconds=duration,
        )

        report_path = None
        if save_report:
            emit_progress(95, "save_report", "Сохраняем отчёт…")
            report_path = _save_report(report_markdown, registry_number, config.data_dir)

        result = TenderAnalysisResult(
            status=overall_status,
            registry_number=registry_number,
            sections=sections,
            sections_count=len(sections),
            sources_count=sources_count,
            analysis_mode=analysis_mode,
            report_markdown=report_markdown,
            report_path=report_path,
            used_llm=use_llm and llm_client is not None,
            llm_model=config.local_llm_model if use_llm else None,
            llm_endpoint=config.local_llm_base_url if use_llm else None,
            retrieval_provider=retrieval_provider,
            retrieval_model=retrieval_model,
            retrieval_limit_used=mode_config.retrieval_limit,
            duration_seconds=round(duration, 4),
            timings=timings,
            per_section_timings=per_section_timings,
            llm_calls_count=llm_calls_count,
            total_context_chars=total_context_chars,
            max_section_context_chars=max_section_context_chars_value,
            avg_section_llm_seconds=avg_section_llm_seconds,
            warnings=warnings,
            errors=errors,
        )
        if record_history:
            emit_progress(98, "record_history", "Сохраняем run в history…")
            run_id = _record_history(result, session, duration_seconds=duration, source=history_source)
            result = replace(result, run_id=run_id)
        emit_progress(100, "completed", "Анализ завершён.")
        return result
    finally:
        if platform_client is not None:
            platform_client.close()
        if own_session:
            session.close()


def _retrieval_only_answer(hits: list[RagSearchHit]) -> str:
    lines = ["Релевантные фрагменты из документов:", ""]
    for idx, hit in enumerate(hits[:6], start=1):
        lines.append(f"[Фрагмент {idx}]")
        lines.append(f"  Документ: {hit.file_name}")
        lines.append(f"  Раздел: {hit.chunk_index}")
        lines.append(f"  Релевантность: {hit.score:.4f}")
        lines.append("  Текст:")
        for text_line in hit.text.strip().split("\n")[:10]:
            lines.append(f"    {text_line}")
        lines.append("")
    return "\n".join(lines)
