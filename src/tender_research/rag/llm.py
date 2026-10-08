from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.tender_research.rag.search_types import RagSearchHit


@dataclass(frozen=True)
class SourceCitation:
    chunk_id: str
    registry_number: str | None
    tender_title: str
    customer_name: str | None
    document_id: str
    document_file_name: str
    score: float
    quote_preview: str


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[SourceCitation]
    used_chunks_count: int
    model: str
    error: str | None = None


def build_source_citations(contexts: Sequence[RagSearchHit]) -> list[SourceCitation]:
    return [
        SourceCitation(
            chunk_id=context.chunk_id,
            registry_number=context.registry_number,
            tender_title=context.tender_title,
            customer_name=context.customer_name,
            document_id=context.document_id,
            document_file_name=context.file_name,
            score=context.score,
            quote_preview=context.preview,
        )
        for context in contexts
    ]


# Source identifiers are supplied to the LLM as opaque values; a UUID can
# be silently mutated while the surrounding prose appears correct.
_CITED_UUID = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{12}(?![0-9a-f])",
    re.IGNORECASE,
)
_EXPLICIT_CHUNK_ID = re.compile(r"chunk_id\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)


def _validate_source_bound_completion(
    response_payload: dict[str, Any],
    answer: str,
    contexts: Sequence[RagSearchHit],
) -> str | None:
    """Fail closed on untraceable source IDs or incomplete model output.

    This guard proves *identity of cited chunks only*. It does not claim that
    the factual statements are entailed by those chunks.
    """
    choices = response_payload.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else {}
    finish_reason = first.get("finish_reason") if isinstance(first, dict) else None
    if finish_reason in {"length", "content_filter"}:
        return "Local LLM answer was truncated or filtered; source claims unverified."
    if finish_reason not in {None, "stop", "eos_token"}:
        return "Local LLM completion finish reason is unverified."

    available = {str(item.chunk_id).strip() for item in contexts if item.chunk_id}
    references = _CITED_UUID.findall(answer)
    references.extend(_EXPLICIT_CHUNK_ID.findall(answer))
    references = [item.strip("[]()<>.\"'") for item in references]
    if not references:
        return "Local LLM answer has no verifiable source chunk citations."
    if any(item not in available for item in references):
        return "Local LLM answer cites unknown or modified source chunk identifiers."
    return None


class LocalChatLlmClient:
    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: int = 120,
        max_context_chars: int = 10_000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_context_chars = max_context_chars

    def generate_answer(
        self,
        question: str,
        contexts: Sequence[RagSearchHit],
        registry_number: str | None = None,
        *,
        analysis_mode: str = "balanced",
    ) -> RagAnswer:
        if not contexts:
            return RagAnswer(
                answer="В найденных документах недостаточно информации для ответа.",
                sources=[],
                used_chunks_count=0,
                model=self.model_name,
                error="No retrieved context was provided to the local LLM.",
            )

        selected_contexts = self._select_contexts_within_budget(contexts)
        if not selected_contexts:
            return RagAnswer(
                answer="В найденных документах недостаточно информации для ответа.",
                sources=[],
                used_chunks_count=0,
                model=self.model_name,
                error=(
                    "Local LLM context too long: "
                    f"no chunks fit within limit {self.max_context_chars}."
                ),
            )

        return self._generate_with_retry(
            question,
            selected_contexts,
            registry_number=registry_number,
            analysis_mode=analysis_mode,
        )

    def build_prompt_metrics(
        self,
        question: str,
        contexts: Sequence[RagSearchHit],
        registry_number: str | None = None,
        *,
        analysis_mode: str = "balanced",
    ) -> dict[str, int]:
        payload, metrics = self._build_payload(
            question,
            contexts,
            registry_number=registry_number,
            analysis_mode=analysis_mode,
        )
        _ = payload
        return metrics

    def _generate_with_retry(
        self,
        question: str,
        contexts: Sequence[RagSearchHit],
        *,
        registry_number: str | None,
        analysis_mode: str,
    ) -> RagAnswer:
        selected_contexts = list(contexts)
        sources = build_source_citations(selected_contexts)
        payload, _metrics = self._build_payload(
            question,
            selected_contexts,
            registry_number=registry_number,
            analysis_mode=analysis_mode,
        )
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = _read_http_error_body(exc)
            if (
                exc.code in (400, 500)
                and _is_context_limit_error(details)
                and len(selected_contexts) > 1
            ):
                return self._generate_with_retry(
                    question,
                    selected_contexts[:-1],
                    registry_number=registry_number,
                    analysis_mode=analysis_mode,
                )
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error=f"Local LLM request failed with HTTP {exc.code}: {details}",
            )
        except TimeoutError:
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error="Local LLM request timed out.",
            )
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            lowered_reason = str(reason).lower()
            message = (
                "Local LLM request timed out."
                if isinstance(reason, TimeoutError) or "timed out" in lowered_reason
                else f"Local LLM server is unavailable: {reason}"
            )
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error=message,
            )

        try:
            response_payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error="Local LLM returned a non-JSON response.",
            )

        answer = _extract_answer_text(response_payload)
        if not answer:
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error="Local LLM returned an empty response.",
            )

        validation_error = _validate_source_bound_completion(
            response_payload, answer, selected_contexts
        )
        if validation_error:
            return RagAnswer(
                answer="",
                sources=sources,
                used_chunks_count=len(selected_contexts),
                model=self.model_name,
                error=validation_error,
            )

        return RagAnswer(
            answer=answer,
            sources=sources,
            used_chunks_count=len(selected_contexts),
            model=self.model_name,
        )

    def _select_contexts_within_budget(
        self, contexts: Sequence[RagSearchHit]
    ) -> list[RagSearchHit]:
        selected: list[RagSearchHit] = []
        for context in contexts:
            candidate = [*selected, context]
            if len(self._build_context_block(candidate)) > self.max_context_chars:
                break
            selected.append(context)
        return selected

    def _build_payload(
        self,
        question: str,
        contexts: Sequence[RagSearchHit],
        *,
        registry_number: str | None,
        analysis_mode: str,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        context_block = self._build_context_block(contexts)
        system_prompt = self._system_prompt(analysis_mode=analysis_mode)
        user_prompt = self._user_prompt(
            question=question,
            context_block=context_block,
            registry_number=registry_number,
            analysis_mode=analysis_mode,
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        metrics = {
            "context_chars": len(context_block),
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "prompt_chars": len(system_prompt) + len(user_prompt),
        }
        return payload, metrics

    def _build_context_block(self, contexts: Sequence[RagSearchHit]) -> str:
        blocks: list[str] = []
        for index, context in enumerate(contexts, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"[Источник {index}]",
                        f"registry_number: {context.registry_number or '-'}",
                        f"tender_title: {context.tender_title}",
                        f"customer: {context.customer_name or '-'}",
                        f"document: {context.file_name}",
                        f"chunk_id: {context.chunk_id}",
                        "text:",
                        context.text.strip(),
                    ]
                )
            )
        return "\n\n".join(blocks)

    def _system_prompt(self, *, analysis_mode: str) -> str:
        if analysis_mode == "fast":
            detail_rule = "Сделай короткий практический вывод в 3-5 предложениях."
        elif analysis_mode == "detailed":
            detail_rule = (
                "Дай развёрнутый ответ с фактами по каждому релевантному фрагменту."
            )
        else:
            detail_rule = "Дай сбалансированный ответ: краткий вывод и ключевые детали."
        return (
            "Ты отвечаешь на вопросы по закупочным документам.\n"
            "Отвечай только по предоставленным фрагментам.\n"
            "Не используй внешние знания и не додумывай факты.\n"
            'Если данных недостаточно, напиши: "В найденных документах недостаточно информации для ответа."\n'
            "Не делай окончательных юридических выводов.\n"
            "Пиши деловым русским языком.\n"
            f"{detail_rule}\n"
            "В конце ответа обязательно добавь раздел 'Источники'.\n"
            "Каждый источник должен ссылаться на document, chunk_id и registry_number.\n"
            "Не выдумывай источники."
        )

    def _user_prompt(
        self,
        *,
        question: str,
        context_block: str,
        registry_number: str | None,
        analysis_mode: str,
    ) -> str:
        registry_line = (
            f"registry_number_filter: {registry_number}\n" if registry_number else ""
        )
        detail_line = {
            "fast": "Сконцентрируйся только на самых важных условиях без длинных цитат.",
            "balanced": "Выдели ключевые условия и добавь короткие пояснения.",
            "detailed": "Раскрой условия подробнее, но не выходи за рамки контекста.",
        }.get(analysis_mode, "Выдели ключевые условия и добавь короткие пояснения.")
        return (
            f"{registry_line}"
            f"Вопрос:\n{question.strip()}\n\n"
            f"Режим анализа: {analysis_mode}\n"
            f"Инструкция: {detail_line}\n\n"
            "Контекст:\n"
            f"{context_block}\n\n"
            "Сформируй ответ в формате:\n"
            "Краткий ответ:\n"
            "...\n\n"
            "Подробности:\n"
            "...\n\n"
            "Источники:\n"
            "1. <file_name>, chunk_id=<id>, registry_number=<rn>"
        )


def _extract_answer_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
            ):
                parts.append(item["text"].strip())
        return "\n".join(part for part in parts if part).strip()
    return ""


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    return body or exc.reason or "no details"


def _is_context_limit_error(details: str) -> bool:
    lowered = details.lower()
    return "context size" in lowered or "exceeds the available context size" in lowered
