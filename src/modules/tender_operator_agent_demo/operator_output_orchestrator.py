"""Product-owned deterministic construction of analysis output payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        AnalyzedDocument,
    )


def project_build_output_payloads(
    *,
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    analysis_mode: str,
    requirements: dict[str, Any],
    calibrated_risks: list[dict[str, Any]],
    supplier_questions: list[dict[str, Any]],
    tkp_comparison: dict[str, Any] | None,
    economics: dict[str, Any] | None,
    bid_decision: dict[str, Any] | None,
    core_complete: bool,
    quote_inputs_present: bool,
    _build_document_grounded_questions,
    _build_document_grounded_requirements,
    _build_document_grounded_rfq_sections,
    _build_document_grounded_risks,
    _build_goods_economics_payload,
    _build_goods_rfq_payload,
    _build_preliminary_procurement_analysis,
    _classify_procurement_scope,
    _collect_role_text,
    _collect_supply_items,
    _collect_unmerged_source_items,
    _extract_notice_price,
    _extract_requirement_rows,
    _is_goods_supply_table_present,
    _normalize_supplier_questions,
    _safe_datetime,
    _service_okpd2_from_sources,
    _translate_user_text,
    build_complete_goods_positions,
    build_non_goods_economics_payload,
    build_operator_analysis_trace,
    build_operator_requirements_context,
    build_operator_risk_payload,
    build_operator_tender_summary,
    build_provisional_operator_recommendation,
    build_quote_comparison_report,
    candidate_requirement_rows,
    candidate_rfq_sections,
    candidate_risks,
    candidate_supplier_questions,
    delivery_address_from_preliminary,
    detect_procurement_richness,
    extract_contract_term_facts,
    extract_goods_source_facts,
    semantic_procurement_role,
    submission_deadline_from_metadata,
) -> dict[str, dict[str, Any]]:
    rfq_draft = requirements.get("_unverified_llm_rfq_draft")
    technical_spec_text = _collect_role_text(documents, "technical_spec")
    contract_draft_text = _collect_role_text(documents, "contract_draft")
    contract_documents = [doc for doc in documents if doc.role == "contract_draft"]
    if contract_documents:
        contract_draft_status = (
            "present" if any(doc.text for doc in contract_documents) else "parse_failed"
        )
    elif metadata.get("files"):
        contract_draft_status = "absent"
    else:
        contract_draft_status = "unknown"
    notice_text = (
        _collect_role_text(documents, "notice")
        or _collect_role_text(documents, "supporting")
        or metadata["tender_title"]
    )
    scope = _classify_procurement_scope(metadata, documents, notice_text)
    procurement_kind = scope["procurement_primary_scope"]
    if any(
        item.item_type == "service" for item in _collect_supply_items(documents)
    ) and procurement_kind in {"unresolved", "generic"}:
        procurement_kind = "services"
    elif _collect_supply_items(documents) and procurement_kind in {
        "unresolved",
        "generic",
    }:
        procurement_kind = "goods"
    grounded_requirement_rows = _build_document_grounded_requirements(
        documents, procurement_kind
    )
    requirement_rows = (
        candidate_requirement_rows(requirements)
        if analysis_mode == "llm_tender_operator_provider"
        else []
        if procurement_kind in {"services", "rental", "works", "unresolved"}
        else grounded_requirement_rows
        if procurement_kind == "goods"
        else grounded_requirement_rows
        or _extract_requirement_rows(requirements, core_complete, procurement_kind)
    )
    source_facts = extract_goods_source_facts(documents)
    (contract_term_facts, contract_term_conflicts) = extract_contract_term_facts(
        documents
    )
    rich_documents = [
        doc for doc in documents if doc.text and detect_procurement_richness(doc)
    ]
    quote_files_present = quote_inputs_present
    output_warnings = list(metadata.get("warnings", []))
    preliminary_analysis = _build_preliminary_procurement_analysis(
        metadata=metadata,
        documents=documents,
        technical_spec_text=technical_spec_text,
        contract_draft_text=contract_draft_text,
        notice_text=notice_text,
    )
    from src.modules.procurement_source_graph.model import (
        direct_fragments_to_canonical_model,
        legacy_rows_to_canonical_model,
    )
    from src.modules.procurement_source_graph.serialization import (
        provenance_records,
        serialize_graph,
    )
    from src.modules.procurement_source_graph.structured_fragment_collector import (
        StructuredFragmentCollector,
    )

    graph_input_rows = (
        preliminary_analysis.get("service_items")
        or preliminary_analysis.get("spec_table", {}).get("rows", [])
        if procurement_kind == "services"
        else preliminary_analysis.get("supply_items")
        or preliminary_analysis.get("service_items")
        or []
    )
    direct_extracted_items = _collect_unmerged_source_items(documents)
    goods_positions = build_complete_goods_positions(direct_extracted_items)
    direct_fragments = StructuredFragmentCollector().collect_supply_items(
        metadata.get("procurement_id"), direct_extracted_items
    )
    canonical_graph_model = (
        legacy_rows_to_canonical_model(
            metadata.get("procurement_id"), procurement_kind, graph_input_rows
        )
        if procurement_kind == "services"
        and (
            not any(
                "код активации" in (fragment.name or "").lower()
                for fragment in direct_fragments
            )
        )
        else direct_fragments_to_canonical_model(
            metadata.get("procurement_id"),
            procurement_kind,
            direct_fragments,
            graph_input_rows,
        )
    )
    canonical_run_status = (
        "needs_review"
        if canonical_graph_model.unresolved_candidates
        else "completed_with_warnings"
        if canonical_graph_model.quality_issues
        else "completed"
    )
    preliminary_analysis["canonical_procurement_model"] = {
        "procurement_number": canonical_graph_model.procurement_number,
        "procurement_scope": canonical_graph_model.procurement_scope,
        "run_status": canonical_run_status,
        "canonical_items": [
            {
                "canonical_item_id": item.canonical_item_id,
                "official_name": item.official_name,
                "display_name": item.display_name or item.official_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "okpd2": next(
                    (
                        source.fragment.okpd2
                        for (field, source) in item.field_provenance.items()
                        if field == "okpd2"
                    ),
                    None,
                ),
                "ktru": next(
                    (
                        source.fragment.ktru
                        for (field, source) in item.field_provenance.items()
                        if field == "ktru"
                    ),
                    None,
                ),
                "characteristics": item.characteristics,
                "primary_source": item.primary_source.fragment.fragment_key
                if item.primary_source
                else None,
                "evidence_ids": [item.primary_source.fragment.fragment_key]
                if item.primary_source
                else [],
                "field_provenance": {
                    field: source.fragment.fragment_key
                    for (field, source) in item.field_provenance.items()
                },
                "source_document": item.primary_source.fragment.document_instance_id
                if item.primary_source
                else None,
                "source_row_number": item.primary_source.fragment.locator
                if item.primary_source
                else None,
                "name_source_type": "validated_primary"
                if item.primary_source
                else "unresolved",
                "quality_gate_status": item.status,
                "warnings": item.warnings,
                "conflicts": item.conflicts,
                "field_issues": item.field_issues,
            }
            for item in canonical_graph_model.canonical_items
        ],
        "unresolved_candidates": [
            item.canonical_item_id
            for item in canonical_graph_model.unresolved_candidates
        ],
        "production_model_hash": canonical_graph_model.production_model_hash,
        "source_fragments": [
            {
                "fragment_key": fragment.fragment_key,
                "document_instance_id": fragment.document_instance_id,
                "source_type": fragment.source_type,
                "locator": fragment.locator,
                "row_role": fragment.row_role,
                "name": fragment.name,
                "quantity": fragment.quantity,
                "unit": fragment.unit,
                "okpd2": fragment.okpd2,
                "ktru": fragment.ktru,
                "characteristics": list(fragment.characteristics),
                "provenance_kind": fragment.provenance_kind,
                "parent_fragment_key": fragment.parent_fragment_key,
                "characteristic_name": fragment.characteristic_name,
                "characteristic_value": fragment.characteristic_value,
                "characteristic_unit": fragment.characteristic_unit,
                "source_position": fragment.position_number,
            }
            for fragment in direct_fragments
        ],
        "source_graph": serialize_graph(
            canonical_graph_model, direct_fragments, "procurement-source-graph-v2"
        ),
        "provenance_records": [
            record.__dict__ for record in provenance_records(canonical_graph_model)
        ],
    }
    if (
        procurement_kind == "goods"
        and _is_goods_supply_table_present(technical_spec_text)
        and (not preliminary_analysis.get("spec_table", {}).get("rows"))
    ):
        output_warnings.append(
            "Позиции поставки не извлечены из ТЗ/спецификации. Анализ неполный."
        )
    if procurement_kind == "goods" and rich_documents and (not source_facts):
        output_warnings.append(
            "SOURCE_EXTRACTION_LOW_RECALL: rich procurement documents produced no source facts."
        )
    tender_summary = build_operator_tender_summary(
        metadata=metadata,
        documents=documents,
        preliminary_analysis=preliminary_analysis,
        analysis_mode=analysis_mode,
        _safe_datetime=_safe_datetime,
        submission_deadline_from_metadata=submission_deadline_from_metadata,
    )
    requirements_payload = build_operator_requirements_context(
        requirement_rows=requirement_rows,
        preliminary_analysis=preliminary_analysis,
        metadata=metadata,
        documents=documents,
        contract_documents=contract_documents,
        contract_draft_status=contract_draft_status,
        contract_draft_text=contract_draft_text,
        notice_text=notice_text,
        scope=scope,
        procurement_kind=procurement_kind,
        goods_positions=goods_positions,
        output_warnings=output_warnings,
        contract_term_facts=contract_term_facts,
        contract_term_conflicts=contract_term_conflicts,
        economics=economics,
        delivery_address_from_preliminary=delivery_address_from_preliminary,
        _service_okpd2_from_sources=_service_okpd2_from_sources,
        _extract_notice_price=_extract_notice_price,
    )
    claim_bound_mode = analysis_mode == "production_llm_r10_1"
    grounded_questions = _build_document_grounded_questions(procurement_kind, documents)
    supplier_questions_payload = {
        "ambiguities": [
            "Полный LLM-анализ не выполнялся; вопросы собраны детерминированно из документов.",
            "Нужно проверить недостающие первичные документы и коммерческие входы вручную.",
        ]
        if analysis_mode == "fallback_deterministic_adapter"
        else ["Параметры оплаты и допустимость аналогов требуют ручной валидации."],
        "questions": _normalize_supplier_questions(supplier_questions, procurement_kind)
        if claim_bound_mode
        else candidate_supplier_questions(supplier_questions)
        if analysis_mode == "llm_tender_operator_provider" and supplier_questions
        else grounded_questions
        if grounded_questions
        else _normalize_supplier_questions(supplier_questions, procurement_kind),
        "manual_checks": [
            "Согласовать финальный вопросник с оператором.",
            "Не отправлять вопросы поставщикам автоматически из этого интерфейса.",
        ],
    }
    rfq_payload = (
        _build_goods_rfq_payload(metadata, documents)
        if procurement_kind == "goods"
        else {
            "rfq_title": f"RFQ draft / {metadata['tender_title']}",
            "sections": _build_document_grounded_rfq_sections(procurement_kind),
        }
    )
    if analysis_mode == "llm_tender_operator_provider" and rfq_draft:
        draft_sections = candidate_rfq_sections(rfq_draft)
        if draft_sections:
            rfq_payload["sections"] = draft_sections
            subject = rfq_draft.get("email_subject")
            if isinstance(subject, str) and subject.strip():
                rfq_payload["rfq_title"] = (
                    "[Черновик LLM — проверить] " + subject.strip()[:200]
                )
    rfq_payload["supplier_targets"] = [
        item.get("supplier_label", "Поставщик")
        for item in (tkp_comparison or {}).get("suppliers", [])
    ] or ["Поставщик 1", "Поставщик 2", "Поставщик 3"]
    rfq_payload["manual_checks"] = [
        "Проверить RFQ на соответствие исходной закупке.",
        "Отправка RFQ выполняется только человеком вне этого demo UI.",
    ]
    quotes_payload = build_quote_comparison_report(
        tkp_comparison, quote_inputs_present, quote_files_present, analysis_mode
    )
    if procurement_kind == "goods":
        economics_payload = _build_goods_economics_payload(
            metadata, documents, analysis_mode, economics
        )
    else:
        economics_payload = build_non_goods_economics_payload(
            metadata,
            technical_spec_text,
            contract_draft_text,
            notice_text,
            analysis_mode,
            preliminary_analysis,
            economics,
            procurement_kind,
            _extract_notice_price=_extract_notice_price,
        )
    grounded_risks = _build_document_grounded_risks(
        procurement_kind, documents, contract_draft_text
    )
    risk_candidates = (
        candidate_risks(calibrated_risks)
        if analysis_mode == "llm_tender_operator_provider" and calibrated_risks
        else calibrated_risks
        if claim_bound_mode
        else grounded_risks or calibrated_risks
    )
    risks_payload = build_operator_risk_payload(
        risk_candidates, claim_bound_mode, _translate_user_text=_translate_user_text
    )
    (final_recommendation, rationale) = build_provisional_operator_recommendation(
        procurement_kind=procurement_kind,
        core_complete=core_complete,
        quote_files_present=quote_files_present,
        economics=economics,
        preliminary_analysis=preliminary_analysis,
        requirement_rows=requirement_rows,
        supplier_questions_payload=supplier_questions_payload,
        risks_payload=risks_payload,
        economics_payload=economics_payload,
    )
    trace = build_operator_analysis_trace(
        documents=documents,
        metadata=metadata,
        preliminary_analysis=preliminary_analysis,
        rich_documents=rich_documents,
        source_facts=source_facts,
        requirement_rows=requirement_rows,
        procurement_kind=procurement_kind,
        rationale=rationale,
        output_warnings=output_warnings,
        semantic_procurement_role=semantic_procurement_role,
    )
    return {
        "tender_summary": tender_summary,
        "requirements": requirements_payload,
        "supplier_questions": supplier_questions_payload,
        "rfq_draft": rfq_payload,
        "quotes_comparison": quotes_payload,
        "economics": economics_payload,
        "contract_risks": risks_payload,
        "final_recommendation": final_recommendation,
        "trace": trace,
    }
