from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Literal

from pydantic import Field, ValidationError

from src.shared.types.common import APIModel
from src.tender_research.config import load_config
from src.tender_research.rag.schemas import TenderAnalysisResult


class ManagerSynthesis(APIModel):
    recommendation: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    confidence: Literal["low", "medium", "high"] = "low"
    rationale: str = Field(min_length=1)
    strongest_reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    application_requirements: list[str] = Field(default_factory=list)
    execution_risks: list[str] = Field(default_factory=list)
    onsite_required: bool | None = None
    next_actions: list[str] = Field(default_factory=list)
    human_control_required: bool = True


def _fallback(reason: str) -> ManagerSynthesis:
    return ManagerSynthesis(
        recommendation="NEEDS_REVIEW",
        confidence="low",
        rationale="Автоматический итог не подтверждён; требуется ручная проверка.",
        unknowns=[reason],
        next_actions=["Открыть source-grounded отчёт и проверить отмеченный пробел."],
        human_control_required=True,
    )


def _extract_json_text(value: str) -> dict:
    text = (value or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence) and text.endswith(fence):
        text = text[len(fence):]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text[: -len(fence)].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise TypeError("manager synthesis response must be a JSON object")
    return parsed


def _request_json(*, base_url: str, model: str, timeout_seconds: int, prompt: dict) -> dict:
    schema = ManagerSynthesis.model_json_schema()
    bodies = [
        {
            "model": model,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "daily_tender_manager_synthesis",
                    "strict": True,
                    "schema": schema,
                },
            },
            "messages": prompt["messages"],
        },
        {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": prompt["messages"],
        },
        {
            "model": model,
            "temperature": 0,
            "messages": prompt["messages"],
        },
    ]
    last_error: Exception | None = None
    for body in bodies:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            return _extract_json_text(content)
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            last_error = exc
            continue
    raise RuntimeError(
        f"local manager synthesis failed: {type(last_error).__name__ if last_error else 'unknown'}"
    )


def synthesize_manager_brief(
    analysis: TenderAnalysisResult,
    *,
    registry_number: str,
    title: str,
    customer_name: str | None,
    nmck_amount: float | None,
    deadline_text: str | None,
    selection_policy: dict[str, list[str]] | None = None,
    use_llm: bool = True,
) -> ManagerSynthesis:
    if not str(analysis.status).startswith("completed"):
        return _fallback(
            "; ".join(analysis.errors or analysis.warnings or ["deep_analysis_not_completed"])
        )

    if not use_llm:
        return _fallback("manager_synthesis_llm_disabled")

    section_payload = [
        {
            "id": section.id,
            "title": section.title,
            "answer": section.answer,
            "source_count": len(section.sources),
        }
        for section in analysis.sections
    ]
    config = load_config()
    prompt = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты внутренний тендерный аналитик ООО «Арвектум». Сформируй только JSON по заданной схеме. "
                    "Используй исключительно переданный source-grounded анализ закупки. Не додумывай факты. "
                    "Если существенный факт не подтверждён, внеси его в unknowns и выбери NEEDS_REVIEW. "
                    "Применяй переданную selection_policy как правила отбора Арвектум. "
                    "NO_GO допустим только при явном существенном hard_blocker, подтверждённом источниками. "
                    "Если blocker или review_signal требует знания о возможностях Арвектум, которого нет в анализе, "
                    "выбирай NEEDS_REVIEW, а не додумывай отсутствие возможности. "
                    "GO допустим только когда нет существенных блокеров и критичных неизвестных. "
                    "Признаки из non_blockers сами по себе не являются причиной NO_GO. "
                    "Это рекомендация для руководителя, а не разрешение на подачу заявки. "
                    "Никогда не разрешай отправку заявки, подписание, оплату или иное внешнее действие."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "registry_number": registry_number,
                        "title": title,
                        "customer_name": customer_name,
                        "nmck_amount": nmck_amount,
                        "deadline": deadline_text,
                        "analysis_status": analysis.status,
                        "analysis_warnings": analysis.warnings,
                        "analysis_errors": analysis.errors,
                        "selection_policy": selection_policy or {},
                        "sections": section_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    try:
        result = ManagerSynthesis.model_validate(
            _request_json(
                base_url=config.local_llm_base_url,
                model=config.local_llm_model,
                timeout_seconds=config.local_llm_timeout_seconds,
                prompt=prompt,
            )
        )
    except (RuntimeError, ValidationError) as exc:
        return _fallback(f"manager_synthesis_error:{type(exc).__name__}")

    if result.recommendation == "GO" and (analysis.warnings or analysis.errors or result.unknowns):
        return result.model_copy(
            update={
                "recommendation": "NEEDS_REVIEW",
                "confidence": "medium" if result.confidence == "high" else result.confidence,
                "rationale": (
                    result.rationale
                    + " Автоматический GO понижен до NEEDS_REVIEW из-за предупреждений или неизвестных."
                ),
            }
        )
    if not result.human_control_required:
        return result.model_copy(update={"human_control_required": True})
    return result
