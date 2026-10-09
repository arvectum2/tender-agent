"""No legal conclusions from document snippets; existing Data Platform citations only."""

from __future__ import annotations

from src.tender_research.api import _to_analyze_response
from src.tender_research.rag.analysis_service import _build_report_markdown
from src.tender_research.rag.ri223_document_dossier import (
    build_ri223_document_dossier,
    render_ri223_document_dossier,
)
from src.tender_research.rag.schemas import (
    SourceCitation,
    TenderAnalysisResult,
    TenderAnalysisSection,
)


def _source(
    *,
    registry="32616445795",
    chunk="chunk-1",
    preview="Срок оказания услуг — 2027 год.",
):
    return SourceCitation(
        chunk_id=chunk,
        registry_number=registry,
        tender_title="РИ223",
        customer_name="ПАО ТГК",
        document_id="doc-1",
        document_file_name="Техническое задание.docx",
        score=0.93,
        quote_preview=preview,
    )


def _section(section="subject", sources=None, status="retrieval_only"):
    return TenderAnalysisSection(
        id=section,
        title=section,
        question="Что подтверждено?",
        answer="Предварительный текст поиска, не решение",
        status=status,
        sources=list(sources or []),
    )


def _verified_source_facts(lot_count=1):
    facts = [
        {
            "kind": "notice_revision",
            "interpretation": "XML_SOURCE_OBSERVATION_ONLY",
            "evidence": {"source": "RI223_getDocsIP"},
            "fields": {"source_version": "1"},
        }
    ]
    facts.extend(
        {
            "kind": "lot",
            "interpretation": "XML_SOURCE_OBSERVATION_ONLY",
            "evidence": {"source": "RI223_getDocsIP"},
            "fields": {"ordinal_number": str(i)},
        }
        for i in range(1, lot_count + 1)
    )
    return facts


def test_source_quote_bound_dossier_displays_evidence_not_verification():
    sources = [_source(), _source(chunk="chunk-2", preview="Срок: 2027")]
    sections = [_section("subject", sources=sources), _section("contract_terms")]
    dossier = build_ri223_document_dossier(
        law_type="223fz",
        registry_number="32616445795",
        sections=sections,
        source_facts=_verified_source_facts(),
    )
    assert len(dossier) == 7
    technical = dossier[0]
    assert technical["domain"] == "technical_scope"
    assert technical["status"] == "NEEDS_HUMAN_DOCUMENT_REVIEW"
    assert technical["requirements_verified"] is False
    assert technical["supplier_fit"] == "UNKNOWN"
    assert technical["contract_risk"] == "NOT_ASSESSED"
    assert technical["decision"] == "NOT_DECIDED"
    assert technical["lot_scope"] == "LOT_SCOPE_NOT_CONFIRMED"
    assert len(technical["source_excerpts"]) == 2
    assert technical["source_excerpts"][0]["document_id"] == "doc-1"
    assert technical["source_excerpts"][0]["chunk_id"] == "chunk-1"
    assert (
        technical["source_excerpts"][0]["source_excerpt"]
        == "Срок оказания услуг — 2027 год."
    )
    assert dossier[4]["status"] == "NO_CITED_DOCUMENT_EXCERPT"
    assert all(x["supplier_fit"] == "UNKNOWN" for x in dossier)
    report = _build_report_markdown(
        "32616445795",
        sections,
        False,
        None,
        "data_platform",
        "hybrid",
        ri223_document_dossier=dossier,
    )
    assert "Матрица документальных свидетельств" in report
    assert "chunk-1" in report
    assert (
        "Не найдено" not in report
    )  # missing evidence is explicitly not an absence claim
    assert "Проверить полный комплект документации" in report
    assert render_ri223_document_dossier([]) == []
    response = _to_analyze_response(
        TenderAnalysisResult(
            status="completed_with_warnings",
            registry_number="32616445795",
            sections=sections,
            sections_count=len(sections),
            sources_count=2,
            ri223_document_dossier=dossier,
        )
    )
    assert len(response.ri223_document_dossier) == 7
    assert response.sources_count == 2


def test_unverified_regime_and_forged_facts_do_not_trigger_dossier():
    sections = [_section("subject", sources=[_source()])]
    assert (
        build_ri223_document_dossier(
            law_type="44fz",
            registry_number="32616445795",
            sections=sections,
            source_facts=_verified_source_facts(),
        )
        == []
    )
    assert (
        build_ri223_document_dossier(
            law_type="223fz",
            registry_number="32616445795",
            sections=sections,
            source_facts=[],
        )
        == []
    )
    assert (
        build_ri223_document_dossier(
            law_type="223fz",
            registry_number="32616445795",
            sections=sections,
            source_facts=[
                {
                    "kind": "lot",
                    "interpretation": "CLAIM",
                    "evidence": {"source": "OTHER"},
                    "fields": {},
                }
            ],
        )
        == []
    )


def test_cross_registry_and_missing_quote_never_become_document_evidence():
    sections = [
        _section(
            "subject",
            sources=[
                _source(registry="11111111111"),
                _source(chunk="empty", preview=""),
                _source(chunk="valid", preview="Подтверждённый фрагмент"),
            ],
        )
    ]
    dossier = build_ri223_document_dossier(
        law_type="223fz",
        registry_number="32616445795",
        sections=sections,
        source_facts=_verified_source_facts(),
    )
    assert [x["chunk_id"] for x in dossier[0]["source_excerpts"]] == ["valid"]
    assert dossier[0]["status"] == "NEEDS_HUMAN_DOCUMENT_REVIEW"


def test_duplicate_chunks_capped_quotes_and_multilot_scope_unknown():
    items = [
        _source(chunk=f"chunk-{n}", preview="Нужно проверить " * 1000) for n in range(9)
    ]
    sections = [_section("subject", sources=[items[0], items[0], *items[1:]])]
    dossier = build_ri223_document_dossier(
        law_type="223fz",
        registry_number="32616445795",
        sections=sections,
        source_facts=_verified_source_facts(lot_count=2),
    )
    assert len(dossier[0]["source_excerpts"]) == 3
    assert all(len(x["source_excerpt"]) <= 420 for x in dossier[0]["source_excerpts"])
    assert all(x["lot_scope"] == "UNRESOLVED_MULTI_LOT" for x in dossier)
    assert all(
        x["revision_scope"] == "DOCUMENT_REVISION_NOT_CONFIRMED" for x in dossier
    )
    for reference in dossier[0]["source_excerpts"]:
        assert reference["lot_number"] == "UNKNOWN"
        assert reference["lot_binding"] == "UNVERIFIED"
        assert reference["notice_revision"] == "UNKNOWN"
        assert reference["revision_binding"] == "UNVERIFIED"
    report = "\n".join(render_ri223_document_dossier(dossier))
    assert "требуется раздельная проверка" in report
    assert "Привязка цитат к лоту и редакции извещения: НЕ ПОДТВЕРЖДЕНА" in report


def test_no_sections_never_implies_absent_requirements():
    dossier = build_ri223_document_dossier(
        law_type="223fz",
        registry_number="32616445795",
        sections=[],
        source_facts=_verified_source_facts(),
    )
    assert len(dossier) == 7
    assert all(x["status"] == "NO_CITED_DOCUMENT_EXCERPT" for x in dossier)
    assert all(x["analysis_section_status"] == "no_context" for x in dossier)


def test_existing_ri223_analyzer_dispatch_populates_dossier_from_dp_hits():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.analysis_service import analyze_tender
    from src.tender_research.rag.search_types import RagSearchHit

    raw = {
        "source_regime": "223fz",
        "source_subsystem": "RI223",
        "archive_sha256": "a" * 64,
        "notice_versions": [
            {
                "source_version": "1",
                "evidence": {
                    "regime": "223fz",
                    "source": "RI223_getDocsIP",
                    "archive_sha256": "a" * 64,
                    "xml_member": "notice.xml",
                    "xml_sha256": "b" * 64,
                    "xpath": "/purchaseNotice/body/item/purchaseNoticeData",
                },
            }
        ],
    }
    tender = SimpleNamespace(id="source-bound", law_type="223fz", raw_payload=raw)
    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 1
    client = MagicMock()
    client.collection_stats.return_value = {"resources": 1, "embeddings": 1}
    retriever = MagicMock()
    retriever.search_documents.return_value = [
        RagSearchHit(
            chunk_id="original-doc-chunk",
            score=0.8,
            registry_number="32616445795",
            tender_id="source-bound",
            tender_title="Проверка исходных документов",
            customer_name=None,
            document_id="dp-child-doc-1",
            file_name="Техническое задание.docx",
            chunk_index=0,
            preview="Работы исполняются в 2027 году",
            text="Работы исполняются в 2027 году",
        )
    ]
    with (
        patch(
            "src.tender_research.rag.analysis_service.TenderRepository",
            return_value=repo,
        ),
        patch(
            "src.tender_research.rag.analysis_service.load_config",
            return_value=TenderResearchConfig(rag_retrieval_backend="data_platform"),
        ),
        patch(
            "src.tender_research.rag.analysis_service.build_tender_collection_id",
            return_value="tender:real:read-only",
        ),
        patch(
            "src.tender_research.rag.analysis_service.build_data_platform_client",
            return_value=client,
        ),
        patch(
            "src.tender_research.rag.analysis_service.DataPlatformRagRetriever",
            return_value=retriever,
        ),
    ):
        result = analyze_tender(
            "32616445795",
            session=MagicMock(),
            record_history=False,
            use_llm=False,
            analysis_mode="fast",
        )
    assert len(result.ri223_document_dossier) == 7
    assert len(result.ri223_source_observations) == 1
    assert (
        result.ri223_document_dossier[0]["source_excerpts"][0]["chunk_id"]
        == "original-doc-chunk"
    )
    assert "Матрица документальных свидетельств" in result.report_markdown
    assert result.used_llm is False
    assert len(result.sections) == 10
    assert result.ri223_document_dossier[0]["decision"] == "NOT_DECIDED"
    client.close.assert_called_once()
