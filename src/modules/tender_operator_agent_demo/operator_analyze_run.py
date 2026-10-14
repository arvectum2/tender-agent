"""Procurement product: local uploaded-run analysis orchestration.

Preserves original stage progression, safe failover and human-review decisions.
Dependency injection retains original runtime test/extension overrides.
"""
from __future__ import annotations

from typing import Any


def analyze_uploaded_demo_run(
    run_id: str,
    *,
    _load_metadata: Any,
    TenderOperatorUploadedRunStatus: Any,
    append_demo_run_event: Any,
    _save_metadata: Any,
    HTTPException: Any,
    _runtime_ai_provenance: Any,
    _collect_documents: Any,
    _collect_role_text: Any,
    _collect_quote_paths: Any,
    _collect_spreadsheet_sources: Any,
    _enrich_procurement_metadata_from_documents: Any,
    get_supplier_profile: Any,
    score_procurement_document_text: Any,
    _try_run_llm_workflow: Any,
    _classify_controlled_llm_result: Any,
    get_settings: Any,
    build_quote_comparison: Any,
    _serialize_quote_comparison: Any,
    build_economics_summary: Any,
    DEFAULT_TARGET_MARGIN_PERCENT: Any,
    DEFAULT_LOGISTICS_RESERVE_PERCENT: Any,
    DEFAULT_RISK_RESERVE_PERCENT: Any,
    DEFAULT_PAYMENT_DELAY_DAYS: Any,
    _serialize_economics_summary: Any,
    _run_supplier_internet_search: Any,
    _build_output_payloads: Any,
    _build_steps_from_outputs: Any,
    _build_final_recommendation: Any,
    DemoRecommendationCode: Any,
    _persist_outputs: Any,
    TenderOperatorUploadedRunAnalyzeResponse: Any,
    DemoStep: Any,
    DemoStepStatus: Any,
) -> Any:
    metadata = _load_metadata(run_id)
    # A successful manual retry must not present errors from an earlier attempt
    # as if they described the current document analysis. Historical failure
    # events stay in the immutable run event feed for operator audit.
    was_failed = metadata.get("status") == TenderOperatorUploadedRunStatus.FAILED.value
    has_stale_error = any(
        str(item).startswith("Analysis failed safely: ")
        for item in metadata.get("warnings", [])
    )
    if was_failed or has_stale_error:
        previous_status = str(metadata.get("status") or "unknown")
        metadata["warnings"] = [
            item for item in metadata.get("warnings", [])
            if not str(item).startswith("Analysis failed safely: ")
        ]
        metadata["limitations"] = [
            item for item in metadata.get("limitations", [])
            if item != "Fallback report generation failed. Manual operator review required."
        ]
        append_demo_run_event(
            run_id,
            "analysis_retry_started",
            "Повторная обработка сохранённых оригиналов после предыдущей ошибки.",
            {"previous_status": previous_status},
        )
    if not metadata.get("files") and metadata.get("status") == TenderOperatorUploadedRunStatus.DOCS_REQUIRED.value:
        metadata["analysis_status"] = "blocked"
        _save_metadata(run_id, metadata)
        append_demo_run_event(
            run_id,
            "analysis_blocked",
            "Анализ остановлен: документация не получена автоматически, требуется ручная загрузка.",
            {"status": metadata.get("status")},
        )
        raise HTTPException(status_code=409, detail="Документация ещё не загружена. Добавьте файлы вручную и повторите анализ.")

    metadata["status"] = TenderOperatorUploadedRunStatus.ANALYZING.value
    metadata["analysis_mode"] = "analyzing"
    metadata["analysis_status"] = "analyzing"
    _save_metadata(run_id, metadata)
    append_demo_run_event(
        run_id,
        "analysis_started",
        "Запущен контролируемый анализ локального demo-run.",
        {"mode": metadata.get("mode"), "files": len(metadata.get("files", []))},
    )

    try:
        ai_provenance = _runtime_ai_provenance()
        documents = _collect_documents(run_id, metadata)
        warnings = list(dict.fromkeys(metadata.get("warnings", []) + [warning for doc in documents for warning in doc.warnings]))

        # Research the complete extracted corpus independently of the model's
        # token-limited three-role excerpts. Every missing attachment remains
        # visible; a citation locator never implies semantic/legal attestation.
        from src.modules.tender_operator_agent_demo.full_corpus_research import (
            research_full_corpus,
        )

        source_research = research_full_corpus(
            documents, manifest=metadata.get("files"),
        )
        metadata["source_research"] = source_research
        append_demo_run_event(
            run_id,
            "full_corpus_source_research_completed",
            "Индексированы извлечённые оригиналы; цитаты требуют независимой проверки.",
            {
                "documents": source_research["document_count"],
                "extracted": source_research["extracted_document_count"],
                "unread": len(source_research["unread_file_ids"]),
                "topics_not_located": len(source_research["missing_research_topics"]),
            },
        )

        notice_text = _collect_role_text(documents, "notice") or _collect_role_text(documents, "supporting") or metadata["tender_title"]
        technical_spec_text = _collect_role_text(documents, "technical_spec")
        contract_draft_text = _collect_role_text(documents, "contract_draft")
        combined_text = "\n\n".join(doc.text for doc in documents if doc.text)
        quote_paths = _collect_quote_paths(run_id, metadata)
        spreadsheet_sources = _collect_spreadsheet_sources(documents)
        economics_inputs = metadata.get("economics_inputs", {})
        metadata = _enrich_procurement_metadata_from_documents(
            metadata,
            documents=documents,
            combined_text=combined_text,
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
            contract_draft_text=contract_draft_text,
        )
        from src.modules.tender_operator_agent_demo.operator_notice_revision import (
            selected_archived_notice_text,
        )

        # Avoid passing an obsolete first-file notice into LLM/preliminary analysis
        # after a newer exact registry-matched archival revision was selected.
        selected_notice_text = selected_archived_notice_text(
            documents, metadata.get("notice_revision_selected")
        )
        if selected_notice_text:
            notice_text = selected_notice_text

        profile = None if metadata.get("mode") == "procurement_search_intake" else get_supplier_profile()
        doc_relevance = score_procurement_document_text(text=combined_text or "", profile=profile)
        metadata["document_relevance"] = doc_relevance
        append_demo_run_event(
            run_id,
            "relevance_document_scoring_completed",
            f"Скоринг документов выполнен: найдено {len(doc_relevance.get('document_matched_terms', []))} совпадений.",
            {"document_score": doc_relevance.get("document_score")},
        )

        from src.modules.tender_operator_agent_demo.eis_notice_parser import (
            build_notice_priority_prompt_section,
            build_technical_documents_prompt_section,
        )
        procurement = metadata.get("procurement", {})
        priority_section = build_notice_priority_prompt_section(procurement)
        if priority_section and notice_text:
            notice_text = priority_section + "\n\n" + notice_text
        technical_docs_section = build_technical_documents_prompt_section(metadata.get("files", []))
        if technical_docs_section:
            technical_spec_text = technical_docs_section + "\n\n" + (technical_spec_text or "")

        core_complete = bool(technical_spec_text and contract_draft_text and notice_text)
        if not technical_spec_text and combined_text:
            technical_spec_text = combined_text[:6000]
            warnings.append("Технические документы не выделены отдельно; используется общий текст документов.")
        if not contract_draft_text:
            warnings.append("Contract draft text was not fully extracted; contract risks are partially inferred.")

        provider_mode = "llm"
        llm_result = _try_run_llm_workflow(
            run_id=run_id,
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
            contract_draft_text=contract_draft_text,
            quote_paths=quote_paths,
            provider_mode=provider_mode,
        )
        if llm_result is not None:
            llm_classification = _classify_controlled_llm_result(llm_result)
            failed_sections = llm_classification["failed_sections"]
            llm_validation_failed = llm_classification["event_type"] != "llm_analysis_completed"
            ai_provenance.update(
                {
                    "analysis_engine": llm_classification["analysis_engine"],
                    "llm_invoked": True,
                    "llm_calls_count": llm_classification["llm_calls_count"],
                    "fallback_reason": llm_classification["fallback_reason"],
                }
            )
            requirements = llm_result.get("requirements", {})
            calibrated_risks = llm_result.get("contract_risks", [])
            supplier_questions = llm_result.get("supplier_questions", [])
            rfq_draft = llm_result.get("rfq_draft", {})

            from src.modules.tender_operator_agent_demo.full_corpus_research import (
                examine_llm_assertions,
            )

            candidate_statements = [
                item
                for key in (
                    "technical_requirements", "qualification_requirements",
                    "document_requirements", "evaluation_criteria",
                )
                for item in (requirements.get(key, []) if isinstance(requirements, dict) else [])
                if isinstance(item, str)
            ]
            candidate_statements.extend(
                str(item["description"])
                for item in calibrated_risks
                if isinstance(item, dict) and isinstance(item.get("description"), str)
            )
            metadata["source_research_llm_claims"] = examine_llm_assertions(
                source_research, candidate_statements,
            )
            analysis_mode = llm_classification["analysis_mode"]
            if llm_validation_failed:
                warnings.append(
                    (
                        "Контролируемый LLM-анализ не прошёл валидацию для разделов: "
                        + ", ".join(failed_sections)
                        if failed_sections
                        else "Контролируемый LLM-анализ не предоставил сведения о валидации разделов"
                    )
                    + ". Невалидированные результаты не приняты."
                )
            append_demo_run_event(
                run_id,
                llm_classification["event_type"],
                (
                    f"LLM-анализ выполнен через {llm_result.get('resolved_provider', 'llm')}."
                    if not llm_validation_failed
                    else "Контролируемый LLM-анализ завершён с ошибками валидации; "
                    "невалидированные результаты не приняты."
                ),
                {
                    "analysis_mode": analysis_mode,
                    "resolved_provider": llm_result.get("resolved_provider"),
                    "failed_sections": failed_sections,
                    "trace_ids": llm_result.get("trace_ids", []),
                },
            )
        else:
            requirements = {
                "technical_requirements": [],
                "document_requirements": [],
                "qualification_requirements": [],
                "evaluation_criteria": [],
            }
            calibrated_risks = []
            supplier_questions = []
            rfq_draft = {}
            analysis_mode = "fallback_deterministic_adapter"
            # Availability of the Data Platform and a local model socket does
            # not mean this particular controlled workflow invoked a model.
            # Expose the effective mode honestly instead of silently hiding
            # a broad validation/runtime exception as a successful AI run.
            provider_config = str(get_settings().llm_provider or "").lower()
            fallback_reason = (
                "configured_stub_provider"
                if provider_config == "stub"
                else "controlled_llm_workflow_unavailable"
            )
            ai_provenance["analysis_engine"] = "deterministic"
            ai_provenance["llm_invoked"] = False
            ai_provenance["llm_calls_count"] = 0
            ai_provenance["fallback_reason"] = fallback_reason
            append_demo_run_event(
                run_id,
                "stub_analysis_fallback",
                "Полный LLM-анализ не выполнялся; итог включает только ограниченное "
                "детерминированное извлечение и требует проверки специалистом.",
                {"core_complete": core_complete, "fallback_reason": fallback_reason},
            )
        metadata["ai_runtime_provenance"] = ai_provenance

        spreadsheet_comparison = build_quote_comparison(spreadsheet_sources, analysis_mode)
        if spreadsheet_comparison.supplier_quotes_found:
            tkp_comparison = _serialize_quote_comparison(spreadsheet_comparison)
            economics_summary = build_economics_summary(
                quote_comparison=spreadsheet_comparison,
                analysis_mode=analysis_mode,
                target_margin_percent=float(economics_inputs.get("target_margin_percent", DEFAULT_TARGET_MARGIN_PERCENT)),
                logistics_reserve_percent=float(economics_inputs.get("logistics_reserve_percent", DEFAULT_LOGISTICS_RESERVE_PERCENT)),
                risk_reserve_percent=float(economics_inputs.get("risk_reserve_percent", DEFAULT_RISK_RESERVE_PERCENT)),
                payment_delay_days=int(economics_inputs.get("payment_delay_days", DEFAULT_PAYMENT_DELAY_DAYS)),
            )
            economics = _serialize_economics_summary(economics_summary)
        else:
            tkp_comparison = None
            economics = None
        bid_decision = llm_result.get("bid_decision") if llm_result else None

        supplier_search_outcome = _run_supplier_internet_search(
            tender_title=metadata.get("tender_title", ""),
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
        )
        metadata["supplier_search"] = {
            "query": supplier_search_outcome.query_used,
            "total_found": supplier_search_outcome.total_found,
            "suppliers": [
                {"name": s.name, "site": s.site, "snippet": s.snippet[:200], "signals": s.relevance_signals}
                for s in supplier_search_outcome.suppliers
            ],
        }
        if supplier_search_outcome.error:
            append_demo_run_event(run_id, "supplier_search_warning", f"Поиск поставщиков недоступен: {supplier_search_outcome.error}", {})
        elif supplier_search_outcome.total_found:
            append_demo_run_event(
                run_id, "supplier_search_completed", f"Найдено {supplier_search_outcome.total_found} потенциальных поставщиков.",
                {"query": supplier_search_outcome.query_used, "count": supplier_search_outcome.total_found},
            )

        limitations = list(dict.fromkeys(metadata.get("limitations", [])))
        if source_research["unread_file_ids"]:
            limitations.append(
                "Не все исходные файлы извлечены и проиндексированы: "
                + ", ".join(source_research["unread_file_ids"][:12])
                + ". Отсутствие найденных требований не означает их отсутствия в документации."
            )
        if source_research["missing_research_topics"]:
            limitations.append(
                "Поиск по полным извлечённым текстам не нашёл явного фрагмента "
                "для тем: " + ", ".join(source_research["missing_research_topics"][:14])
                + ". Это неопределённость, а не подтверждение отсутствия обязательства."
            )
        limitations.append(
            "Полнотекстовый исследовательский индекс возвращает проверяемые "
            "фрагменты и хеши, но не подтверждает смысл правовых выводов; "
            "структурный PASS LLM также не является проверкой фактов. "
            "Необходима независимая проверка цитат человеком."
        )
        if analysis_mode == "llm_tender_operator_provider":
            limitations.append(
                "Выводы LLM — гипотезы: формальные критерии оценки, допуск, "
                "НМЦК, сроки и изменения цены должны быть отдельно "
                "подтверждены по оригиналам даже при PASSED JSON."
            )
        if analysis_mode == "fallback_deterministic_adapter":
            limitations.append(
                "Полный LLM-анализ документов не выполнялся "
                f"({ai_provenance['fallback_reason']}). "
                "Доступность локальной модели или Data Platform не является "
                "подтверждением анализа закупки; детальные риски и экономика "
                "требуют отдельной проверки."
            )
        if not core_complete:
            limitations.append("Full runner integration was partially applied because the uploaded package did not produce all core extracted texts.")
        quote_inputs_present = bool(quote_paths or spreadsheet_sources)
        if not quote_inputs_present:
            limitations.append("TKP not uploaded. Supplier comparison and economics remain blocked or partial.")
        elif not spreadsheet_sources and quote_paths:
            limitations.append("Quote files were uploaded in non-spreadsheet format; structured comparison and economics require manual review or XLS/XLSX.")
        if spreadsheet_sources:
            limitations.append("Spreadsheet normalization uses deterministic heuristics and may require manual review for нестандартные таблицы.")
            if tkp_comparison:
                limitations.extend(tkp_comparison.get("limitations", []))
            if economics:
                limitations.extend(economics.get("limitations", []))
        elif any(item["extension"] in {".xlsx", ".xls"} for item in metadata.get("files", [])):
            limitations.append("Spreadsheet files were uploaded, but structured extraction could not start.")

        metadata["warnings"] = sorted(set(warnings))
        metadata["limitations"] = limitations
        metadata["analysis_mode"] = analysis_mode
        metadata["analysis_status"] = "completed"

        # Preserve the established public/patch-wrapper function signature.
        # Validated-schema LLM RFQ remains a review-only candidate, never an
        # authenticated factual source or an external communication.
        if analysis_mode == "llm_tender_operator_provider" and isinstance(rfq_draft, dict):
            requirements = {**requirements, "_unverified_llm_rfq_draft": rfq_draft}
        outputs = _build_output_payloads(
            metadata=metadata,
            documents=documents,
            analysis_mode=analysis_mode,
            requirements=requirements,
            calibrated_risks=calibrated_risks,
            supplier_questions=supplier_questions,
            tkp_comparison=tkp_comparison,
            economics=economics,
            bid_decision=bid_decision,
            core_complete=core_complete,
            quote_inputs_present=quote_inputs_present,
        )
        steps = _build_steps_from_outputs(metadata, outputs)
        final_recommendation = _build_final_recommendation(outputs)
        status = TenderOperatorUploadedRunStatus.COMPLETED if core_complete and tkp_comparison else TenderOperatorUploadedRunStatus.COMPLETED_WITH_WARNINGS
        if final_recommendation.recommendation == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED:
            status = TenderOperatorUploadedRunStatus.COMPLETED_WITH_WARNINGS if quote_inputs_present else TenderOperatorUploadedRunStatus.NEEDS_REVIEW

        metadata["status"] = status.value
        _save_metadata(run_id, metadata)
        _persist_outputs(run_id, metadata, outputs, steps)
        append_demo_run_event(
            run_id,
            "analysis_completed",
            "Анализ завершён в контролируемом demo-контуре.",
            {"status": status.value, "analysis_mode": analysis_mode},
        )

        return TenderOperatorUploadedRunAnalyzeResponse(
            run_id=run_id,
            status=status,
            analysis_mode=analysis_mode,
            warnings=metadata["warnings"],
            limitations=metadata["limitations"],
            steps=steps,
            final_recommendation=final_recommendation,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - preserve legacy safe-failure envelope
        metadata["status"] = TenderOperatorUploadedRunStatus.FAILED.value
        metadata["analysis_mode"] = "failed"
        metadata["analysis_status"] = "failed"
        metadata["warnings"] = list(dict.fromkeys(metadata.get("warnings", []) + [f"Analysis failed safely: {exc}"]))
        metadata["limitations"] = list(dict.fromkeys(metadata.get("limitations", []) + ["Fallback report generation failed. Manual operator review required."]))
        _save_metadata(run_id, metadata)
        append_demo_run_event(
            run_id,
            "analysis_blocked",
            "Анализ завершился безопасной остановкой из-за внутренней ошибки.",
            {"error": str(exc)},
        )

        failed_outputs = {
            "final_recommendation": {
                "recommendation": DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value,
                "label": "нужна ручная проверка",
                "rationale": ["Анализ не завершился полностью и был остановлен в безопасном режиме."],
                "key_requirements": ["Проверка пакета документов вручную"],
                "open_questions": ["Нужно повторно проверить загруженные файлы и формат документов."],
                "risks": ["Автоматический анализ не завершён"],
                "economics": ["Недостаточно данных"],
                "manual_checks": ["Повторно просмотреть пакет документов вручную."],
            },
            "trace": {
                "overall_explanation": "Система не выполнила внешних действий и остановила анализ в безопасном режиме после внутренней ошибки.",
                "per_step": {step: "Анализ остановлен в safe mode." for step in ("documents", "requirements", "supplier_search", "questions", "rfq", "quotes", "economics", "risks", "decision")},
                "limitations": metadata["limitations"],
            },
        }
        final_recommendation = _build_final_recommendation(failed_outputs)
        steps = [
            DemoStep(
                key="documents",
                order=1,
                title="Документы",
                short_title="Документы",
                status=DemoStepStatus.NEEDS_REVIEW,
                description="Анализ остановлен до полного прохождения pipeline.",
                agent_action="Система сохранила локальные файлы, но не завершила разбор.",
                result_summary="Run остановлен в safe mode.",
                findings=metadata["warnings"],
                human_review=["Проверить формат и содержимое загруженных файлов вручную."],
                trace="Безопасная остановка без внешних действий.",
                result_sections=[],
            )
        ]
        return TenderOperatorUploadedRunAnalyzeResponse(
            run_id=run_id,
            status=TenderOperatorUploadedRunStatus.FAILED,
            analysis_mode="failed",
            warnings=metadata["warnings"],
            limitations=metadata["limitations"],
            steps=steps,
            final_recommendation=final_recommendation,
        )
