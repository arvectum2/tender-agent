"""Isolated product-specific controlled LLM execution with human-only guardrails.

Generic model invocation/transport remains shared; this component supplies
only procurement-specific prompt context and fail-closed event classification.
The legacy wrapper preserves test monkeypatch and call compatibility.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.modules.tender_operator_agent_demo.document_context_selection import (
    select_document_context,
)
from src.shared.config.settings import get_settings


def run_controlled_operator_llm(
    run_id: str,
    notice_text: str | None,
    technical_spec_text: str | None,
    contract_draft_text: str | None,
    quote_paths: list[Path],
    provider_mode: str = "llm",
    emit_event: Callable[..., Any] | None = None,
    settings_getter: Callable[[], Any] = get_settings,
) -> dict[str, Any] | None:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from src.modules.controlled_llm_prebid.service import (
            run_controlled_tender_operator_workflow,
        )

        # Register all ORM tables before create_all: controlled trace models
        # have foreign keys to product tables that partial imports omit.
        from src.shared.db import models as _registered_models  # noqa: F401
        from src.shared.db.base import Base

        settings = settings_getter()
        if not settings.database_url:
            return None

        engine = create_engine(settings.database_url)
        Base.metadata.create_all(engine)

        selected_notice = select_document_context(notice_text or "", role="notice")
        selected_spec = select_document_context(technical_spec_text or "", role="technical_spec")
        selected_contract = select_document_context(contract_draft_text or "", role="contract_draft")
        context = {
            "deal_id": f"DEMO-{run_id}",
            "operator_id": "tender_operator_demo",
            "operator_profile": {},
            "documents": {
                "notice_text": selected_notice.text,
                "technical_spec_text": selected_spec.text,
                "contract_draft_text": selected_contract.text,
            },
            "workflow_guardrails": {
                "manual_only": True,
                "no_email_send": True,
                "no_platform_submission": True,
                "human_review_required": True,
            },
            "tkp_inputs": [],
        }
        with Session(engine) as session:
            result = run_controlled_tender_operator_workflow(
                session,
                provider_mode=provider_mode,
                context=context,
                include_quote_normalization=False,
                include_bid_decision=False,
                simulate_invalid_output=False,
                provider_name_override=None,
            )
            return {
                "analysis_mode": result.analysis_mode,
                "resolved_provider": result.resolved_provider,
                "sections": result.sections,
                "trace_ids": result.trace_ids,
                "requirements": result.requirements,
                "supplier_questions": result.supplier_questions,
                "rfq_draft": result.rfq_draft,
                "contract_risks": result.contract_risks,
                "bid_decision": result.bid_decision,
            }
    except Exception as exc:  # noqa: BLE001 - fail-closed LLM/DB boundary
        # The previous catch-all silently turned every LLM/DB/provider error
        # into a "successful" deterministic run. Log only the exception class:
        # provider exception text can include credentials or document content.
        if emit_event is not None:
            emit_event(
                run_id,
                "controlled_llm_runtime_failed",
            "Контролируемый LLM-анализ не запустился; результаты модели не использованы.",
                {"error_type": type(exc).__name__, "provider_mode": provider_mode},
            )
        return None
