from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from pathlib import Path
import re
import time
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.tender_research.config import load_config
from src.tender_research.rag.embeddings import build_embedding_provider
from src.tender_research.rag.history_service import record_analysis_run
from src.tender_research.rag.llm import (
    LocalChatLlmClient,
    build_source_citations,
)
from src.tender_research.rag.prepare_service import sync_tender_from_operator_run
from src.tender_research.rag.retriever import RagRetriever, RagSearchHit
from src.tender_research.rag.schemas import (
    ANALYSIS_SECTIONS,
    ANALYSIS_MODE_CHOICES,
    DEFAULT_ANALYSIS_MODE,
    SourceCitation,
    TenderAnalysisResult,
    TenderAnalysisSection,
)
from src.tender_research.rag.vector_store import JsonVectorStore
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


def _source_fact_value(source_facts: str | None, label: str) -> str | None:
    if not source_facts:
        return None
    prefix = f"{label}:"
    for raw_line in source_facts.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            return value or None
    return None


def _preserve_structured_deadline(
    section_id: str,
    answer: str,
    source_facts: str | None,
) -> str:
    """Keep source timezone in deadline answers even if the LLM shortens it."""
    if section_id != "deadlines" or not answer:
        return answer
    deadline = _source_fact_value(source_facts, "Окончание подачи заявок")
    if not deadline or deadline in answer:
        return answer
    match = re.match(r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})", deadline)
    if match and match.group(1) in answer:
        return answer.replace(match.group(1), deadline)
    return f"Подтверждённый срок подачи заявок: {deadline}.\n\n{answer}"


def _slugify(value: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "default"


_DEFAULT_HASH_PROVIDER_NAMES = {"hash", "hashing", "local_hash"}
_STRUCTURED_FACT_SECTION_IDS = {
    "notice_info",
    "subject",
    "application_composition",
    "restrictions_benefits",
    "deadlines",
    "documents_summary",
}

_FOCUSED_SECTION_QUERIES: dict[str, tuple[str, ...]] = {
    "subject": (
        "Объект закупки Тип позиции Услуга Единица измерения Условная единица Количество объем работы услуги Стоимость позиции",
        "62.02.30.000 Услуга Условная единица 521000",
    ),
    "contract_terms": (
        "Авансовые платежи по Контракту не предусмотрены; 100 процентов в течение 7 рабочих дней после приемки",
        "Услуга должна быть оказана до 13.11.2026; срок исполнения контракта",
        "Размер обеспечения исполнения контракта 10 процентов",
        "Заказчик подписывает документ о приемке в течение рабочих дней",
        "неустойка штраф пеня ответственность Исполнителя",
    ),
    "application_composition": (
        "декларация о соответствии пунктам 3 5 7 11 части 1 статьи 31 реквизиты счета предложение о цене контракта",
        "порядковый номер реестровой записи российского программного обеспечения статья 14 национальный режим",
        "информация и документы оператор электронной площадки не включаются участником в заявку",
    ),
    "restrictions_benefits": (
        "Преимущество в соответствии с ч. 3 ст. 30 Закона № 44-ФЗ",
        "Постановление Правительства 1875 запрет услуги иностранных лиц национальный режим",
        "СМП СОНКО часть 8.1 статьи 96 освобождается от обеспечения исполнения контракта",
        "обеспечение гарантийных обязательств не требуется",
    ),
}


def _focused_queries_for_section(section_id: str) -> tuple[str, ...]:
    return _FOCUSED_SECTION_QUERIES.get(section_id, ())


def _structured_fact_citation(
    *,
    registry_number: str,
    tender_title: str,
    customer_name: str | None,
    source_facts: str,
    source_label: str = "Карточка ЕИС — структурированные факты",
) -> SourceCitation:
    source_id = "structured-facts:" + registry_number
    return SourceCitation(
        chunk_id=source_id,
        registry_number=registry_number,
        tender_title=tender_title,
        customer_name=customer_name,
        document_id=source_id,
        document_file_name=source_label,
        score=1.0,
        quote_preview=source_facts,
    )


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip(" .;\n\t")


def _notice_source_facts(repo: TenderRepository, tender) -> str:
    """Extract bounded purchase-object and restriction facts from the EIS notice."""
    notice_parts: list[str] = []
    for doc in repo.list_extracted_documents_by_tender(tender.id):
        name = str(doc.file_name or "").lower()
        if "извещ" not in name:
            continue
        path = Path(str(doc.extracted_text_path or ""))
        if not path.is_file():
            continue
        try:
            notice_parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    text = "\n".join(notice_parts)
    if not text:
        return ""

    facts: list[str] = []
    row = re.search(
        r"Объект закупки\s*"
        r"Наименование товара, работы, услуги.*?"
        r"Стоимость позиции"
        r"(?P<name>.+?)"
        r"Идентификатор:\s*(?P<identifier>\d+?)"
        r"(?P<okpd2>\d{2}\.\d{2}\.\d{2}\.\d{3})"
        r"Услуга"
        r"(?P<unit>Условная единица)"
        r"(?P<unit_price>\d+(?:[.,]\d{2})?)"
        r"(?P<tail>.+?)"
        r"Характеристики товара, работы, услуги",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if row:
        numeric_match = re.search(r"(?P<numeric>[0-9.,]+)\s*$", re.sub(r"\s+", " ", row.group("tail")).strip())
        if numeric_match:
            suffix = numeric_match.group("numeric")
            unit_price = float(row.group("unit_price").replace(",", "."))
            for split_at in range(1, len(suffix)):
                quantity_raw, total_raw = suffix[:split_at], suffix[split_at:]
                if not re.fullmatch(r"\d+(?:[.,]\d+)?", quantity_raw):
                    continue
                if not re.fullmatch(r"\d+[.,]\d{2}", total_raw):
                    continue
                quantity = float(quantity_raw.replace(",", "."))
                total = float(total_raw.replace(",", "."))
                if abs(unit_price * quantity - total) <= max(0.01, abs(total) * 0.001):
                    normalized_name = re.sub(r"\s+", " ", row.group("name")).strip()
                    facts.extend(
                        [
                            f"Позиция закупки: {normalized_name}",
                            f"ОКПД2: {row.group('okpd2')}",
                            f"Тип позиции: услуга",
                            f"Единица измерения: {row.group('unit')}",
                            f"Количество (объём): {quantity_raw}",
                            f"Цена за единицу: {row.group('unit_price')} RUB",
                            f"Стоимость позиции: {total_raw} RUB",
                        ]
                    )
                    break

    advantage = _first_match(
        text,
        r"(Преимущество\s+в\s+соответствии\s+с\s+ч\.\s*3\s+ст\.\s*30\s+Закона\s+№\s*44-ФЗ)",
    )
    if advantage:
        facts.append(f"Преимущество закупки: {advantage}")
    if "Постановление Правительства Российской Федерации" in text and "№ 1875" in text:
        facts.append("Национальный режим: применяется Постановление Правительства РФ № 1875.")
    if re.search(r"Запрет закупок[^\n]{0,500}?услуг иностранными лицами", text, re.IGNORECASE):
        facts.append("Национальный режим: установлен запрет на услуги, оказываемые иностранными лицами.")
    if re.search(r"Обеспечение заявок не требуется", text, re.IGNORECASE):
        facts.append("Обеспечение заявки: не требуется.")
    if re.search(r"Обеспечение гарантийных обязательств не требуется", text, re.IGNORECASE):
        facts.append("Обеспечение гарантийных обязательств: не требуется.")
    return "\n".join(facts)


def _contract_source_facts(repo: TenderRepository, tender) -> str:
    """Extract a small deterministic contract fact set from current source text."""
    contract_parts: list[str] = []
    technical_parts: list[str] = []
    notice_parts: list[str] = []
    for doc in repo.list_extracted_documents_by_tender(tender.id):
        path = Path(str(doc.extracted_text_path or ""))
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        name = str(doc.file_name or "").lower()
        if "контракт" in name:
            contract_parts.append(text)
        elif "техничес" in name or "задан" in name:
            technical_parts.append(text)
        elif "извещ" in name:
            notice_parts.append(text)

    contract_text = "\n".join(contract_parts)
    technical_text = "\n".join(technical_parts)
    notice_text = "\n".join(notice_parts)
    facts: list[str] = []

    service_term = _first_match(
        contract_text + "\n" + technical_text,
        r"Услуга должна быть оказана[^.\n]*?до\s+(\d{2}\.\d{2}\.\d{4})",
    )
    if service_term:
        facts.append(f"Срок оказания услуг: до {service_term}")

    execution_term = _first_match(
        contract_text + "\n" + notice_text,
        r"Срок исполнения контракта[^\n\d]*(\d{2}\.\d{2}\.\d{4})",
    )
    if execution_term:
        facts.append(f"Срок исполнения контракта: до {execution_term}")

    if re.search(r"Авансовые платежи[^.]{0,120}не предусмотр", contract_text, re.IGNORECASE):
        facts.append("Аванс: не предусмотрен")

    payment = _first_match(
        contract_text,
        r"Расчет за оказанные услуги\s+осуществляется\s+([^\.]+)",
    )
    if payment:
        facts.append(f"Оплата: {payment}")

    security = _first_match(
        notice_text + "\n" + contract_text,
        r"Размер обеспечения исполнения контракта[^%\n]{0,220}?(\d+(?:[.,]\d+)?)\s*%",
    )
    if security:
        facts.append(f"Обеспечение исполнения контракта: {security.replace('.', ',')}%")

    warranty = _first_match(
        technical_text,
        r"Гарантийные обязательства\s+Гарантия\s+([^\.]+)",
    )
    if warranty:
        facts.append(f"Гарантия: {warranty}")
    remediation = _first_match(
        technical_text,
        r"Срок устранения\s*[–-]\s*([^\.]+)",
    )
    if remediation:
        facts.append(f"Срок устранения недостатков: {remediation}")

    return "\n".join(facts)


def _vector_store_path(config, *, provider_name: str, model_name: str) -> str:
    if config.rag_vector_store_path:
        raw_path = config.rag_vector_store_path.format(
            provider=_slugify(provider_name),
            model=_slugify(model_name),
        )
        path = Path(raw_path)
    else:
        path = Path(config.data_dir) / "rag" / "vector_store.json"

    provider_alias = (config.rag_embeddings_provider or provider_name).strip().lower()
    if provider_alias in _DEFAULT_HASH_PROVIDER_NAMES and model_name == "local-hash-v1":
        return str(path)

    suffix = path.suffix or ".json"
    stem = path.stem if path.suffix else path.name
    named = f"{stem}__{_slugify(provider_name)}__{_slugify(model_name)}{suffix}"
    return str(path.with_name(named))


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
    source_facts: str | None = None,
) -> str:
    unique_chunks = {
        source.chunk_id
        for section in sections
        for source in section.sources
        if source.chunk_id
    }
    unique_documents = {
        source.document_file_name
        for section in sections
        for source in section.sources
        if source.document_file_name
    }
    citation_uses = sum(len(section.sources) for section in sections)
    lines = [
        f"# Анализ закупки {registry_number}",
        "",
        f"**Статус:** завершено",
        f"**Режим анализа:** {analysis_mode}",
        f"**LLM:** {'да' if used_llm else 'нет'} {f'({llm_model})' if llm_model and used_llm else ''}",
        f"**Поиск:** {retrieval_provider or '?'} / {retrieval_model or '?'}",
        f"**Разделов:** {len(sections)}",
        f"**Уникальных источников (включая структурированную карточку):** {len(unique_documents)}",
        f"**Уникальных фрагментов:** {len(unique_chunks)}",
        f"**Использований источников по разделам:** {citation_uses}",
        "",
    ]
    if duration_seconds is not None:
        lines.append(f"**Длительность:** {duration_seconds:.2f} сек")
    if source_facts and source_facts.strip():
        lines.extend(
            [
                "",
                "## Подтверждённые факты карточки закупки",
                "",
                *[f"- {line}" for line in source_facts.strip().splitlines() if line.strip()],
            ]
        )
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
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
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
    except Exception as e:
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

        if provider:
            object.__setattr__(config, "rag_embeddings_provider", provider)
            if provider.strip().lower() not in _DEFAULT_HASH_PROVIDER_NAMES:
                object.__setattr__(config, "rag_embedding_dimension", None)
        if model:
            object.__setattr__(config, "rag_embeddings_model", model)
        if base_url:
            object.__setattr__(config, "rag_embeddings_base_url", base_url)
        if timeout_seconds:
            object.__setattr__(config, "rag_embeddings_timeout_seconds", timeout_seconds)
        if batch_size:
            object.__setattr__(config, "rag_embeddings_batch_size", batch_size)
        if llm_base_url:
            object.__setattr__(config, "local_llm_base_url", llm_base_url)
        if llm_model:
            object.__setattr__(config, "local_llm_model", llm_model)
        object.__setattr__(config, "local_llm_timeout_seconds", mode_config.llm_timeout_seconds)

        repo = TenderRepository(session)
        try:
            tender = sync_tender_from_operator_run(repo, registry_number)
        except Exception:
            logger.exception(
                "Failed to refresh operator-run metadata for %s; using stored RAG tender",
                registry_number,
            )
            tender = None
        if tender is None:
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

        raw_payload = tender.raw_payload if isinstance(tender.raw_payload, dict) else {}
        document_inventory = [
            str(item).strip()
            for item in (raw_payload.get("document_inventory") or [])
            if str(item).strip()
        ]
        if not document_inventory:
            document_inventory = [
                doc.file_name
                for doc in repo.list_extracted_documents_by_tender(tender.id)
                if doc.file_name
            ]
        deadline_source_text = str(
            raw_payload.get("application_deadline_source_text") or ""
        ).strip()
        publication_source_text = str(
            raw_payload.get("publication_date_source_text") or ""
        ).strip()
        source_fact_lines = [
            f"Номер закупки: {registry_number}",
            f"Предмет: {tender.title}",
            f"Заказчик: {tender.customer_name or 'не указан'}",
            f"Закон: {raw_payload.get('procurement_law') or tender.law_type or 'не указан'}",
            f"Способ закупки: {raw_payload.get('procedure_type_source_text') or 'не указан'}",
            f"Статус закупки: {raw_payload.get('status_source_text') or tender.status or 'не указан'}",
            (
                f"Дата публикации: {publication_source_text}"
                if publication_source_text
                else (
                    f"Дата публикации: {tender.publication_date.isoformat()}"
                    if tender.publication_date
                    else "Дата публикации: не указана"
                )
            ),
            (
                f"Окончание подачи заявок: {deadline_source_text}"
                if deadline_source_text
                else (
                    f"Окончание подачи заявок (UTC): {tender.application_deadline.isoformat()}"
                    if tender.application_deadline
                    else "Окончание подачи заявок: не указано"
                )
            ),
            (
                f"НМЦК: {raw_payload.get('nmck_source_value') or tender.nmck_amount} "
                f"{tender.currency or 'RUB'}"
                if (raw_payload.get("nmck_source_value") is not None or tender.nmck_amount is not None)
                else "НМЦК: не указана"
            ),
        ]
        if document_inventory:
            source_fact_lines.append(
                "Состав полученной документации: " + "; ".join(document_inventory)
            )
        source_facts = "\n".join(source_fact_lines)
        notice_source_facts = _notice_source_facts(repo, tender)
        contract_source_facts = _contract_source_facts(repo, tender)

        emb_provider = build_embedding_provider(config)
        vector_store = JsonVectorStore(
            _vector_store_path(config, provider_name=emb_provider.provider_name, model_name=emb_provider.model_name),
            dimension=emb_provider.dimension or None,
        )
        retriever = RagRetriever(repo, emb_provider, vector_store)
        emit_progress(10, "retrieval", "Подготавливаем поиск по документам…")

        embeddings_count = repo.count_document_embeddings(
            provider=emb_provider.provider_name,
            model=emb_provider.model_name,
        )
        if embeddings_count == 0:
            result = TenderAnalysisResult(
                status="no_context",
                registry_number=registry_number,
                sections=[],
                sections_count=0,
                sources_count=0,
                analysis_mode=analysis_mode,
                errors=[f"No embeddings found for provider={emb_provider.provider_name} model={emb_provider.model_name}. Run build-embeddings first."],
                retrieval_provider=emb_provider.provider_name,
                retrieval_model=emb_provider.model_name,
                retrieval_limit_used=mode_config.retrieval_limit,
            )
            if record_history:
                _record_history(result, session, duration_seconds=0.0, source=history_source)
            return result

        llm_client: LocalChatLlmClient | None = None
        if use_llm:
            try:
                llm_client = LocalChatLlmClient(
                    base_url=config.local_llm_base_url,
                    model_name=config.local_llm_model,
                    timeout_seconds=mode_config.llm_timeout_seconds,
                    max_context_chars=mode_config.max_context_chars_per_section,
                )
            except Exception as e:
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
            focused_queries = _focused_queries_for_section(sec_def["id"])
            if focused_queries:
                priority_hits: list[RagSearchHit] = []
                for focused_query in focused_queries:
                    priority_hits.extend(
                        retriever.search_documents(
                            focused_query,
                            registry_number=registry_number,
                            limit=1,
                        )
                    )
                seen_priority: set[str] = set()
                merged_hits: list[RagSearchHit] = []
                for hit in [*priority_hits, *hits]:
                    if hit.chunk_id in seen_priority:
                        continue
                    seen_priority.add(hit.chunk_id)
                    merged_hits.append(hit)
                hits = merged_hits
            retrieval_seconds = time.perf_counter() - retrieval_started_at
            retrieval_seconds_total += retrieval_seconds
            sources = build_source_citations(hits)
            if sec_def["id"] == "contract_terms" and contract_source_facts:
                section_source_facts = contract_source_facts
                structured_source_label = "Проект контракта и ТЗ — структурированные факты"
            elif sec_def["id"] in {"subject", "restrictions_benefits"} and notice_source_facts:
                section_source_facts = "\n".join(
                    part for part in (source_facts, notice_source_facts) if part
                )
                structured_source_label = "Извещение ЕИС — структурированные факты"
            elif sec_def["id"] in _STRUCTURED_FACT_SECTION_IDS:
                section_source_facts = source_facts
                structured_source_label = "Карточка ЕИС — структурированные факты"
            else:
                section_source_facts = None
                structured_source_label = "Структурированные факты источников"
            if section_source_facts:
                sources = [
                    _structured_fact_citation(
                        registry_number=registry_number,
                        tender_title=tender.title,
                        customer_name=tender.customer_name,
                        source_facts=section_source_facts,
                        source_label=structured_source_label,
                    ),
                    *sources,
                ]
            all_sources.extend(sources)
            section_max_chunks = (
                max(mode_config.max_chunks_per_section, 5)
                if sec_def["id"] == "contract_terms"
                else mode_config.max_chunks_per_section
            )
            section_max_chunk_chars = (
                max(mode_config.max_chunk_chars, 1_200)
                if sec_def["id"] == "contract_terms"
                else mode_config.max_chunk_chars
            )
            section_max_context_chars = (
                max(mode_config.max_context_chars_per_section, 6_000)
                if sec_def["id"] == "contract_terms"
                else mode_config.max_context_chars_per_section
            )
            section_context = build_section_context(
                hits,
                max_chunks=section_max_chunks,
                max_context_chars=section_max_context_chars,
                max_chunk_chars=section_max_chunk_chars,
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
                    source_facts=section_source_facts,
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
                    source_facts=section_source_facts,
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
                    answer_text = _preserve_structured_deadline(
                        sec_def["id"],
                        answer.answer,
                        section_source_facts,
                    )
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

        sources_count = len(set(source.chunk_id for source in all_sources))
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
            retrieval_provider=emb_provider.provider_name,
            retrieval_model=emb_provider.model_name,
            analysis_mode=analysis_mode,
            duration_seconds=duration,
            source_facts=source_facts,
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
            retrieval_provider=emb_provider.provider_name,
            retrieval_model=emb_provider.model_name,
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
