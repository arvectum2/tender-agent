from pathlib import Path


def test_data_platform_adapter_contains_no_procurement_decision_logic() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "tender_research"
        / "rag"
        / "data_platform.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "DecisionCore",
        "CommercialCore",
        "GO_NO_GO",
        "supplier_compatibility",
        "44_fz_rule",
        "223_fz_rule",
    )
    assert not any(token in source for token in forbidden)


def test_boundary_document_declares_dependency_direction() -> None:
    text = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "tender_research"
        / "data_platform_boundary.md"
    ).read_text(encoding="utf-8")
    assert "Tender Agent -> Data Platform" in text
    assert "Data Platform -> Tender Agent" not in text


def test_document_recovery_uses_data_platform_chunk_builder() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "modules"
        / "production_llm_analysis"
        / "document_recovery.py"
    ).read_text(encoding="utf-8")
    assert "build_recovery_chunk_indexer" in source
    assert "DocumentChunkIndexer" not in source
    assert "extract_document_with_data_platform" in source
    assert "_try_extract" not in source
    assert "rag.chunker" not in source
    assert "rag.indexer" not in source


def test_data_platform_runtime_has_no_top_level_legacy_rag_imports() -> None:
    import ast

    root = Path(__file__).resolve().parents[2]
    forbidden = {
        "src.tender_research.rag.chunker",
        "src.tender_research.rag.embeddings",
        "src.tender_research.rag.indexer",
        "src.tender_research.rag.retriever",
        "src.tender_research.rag.vector_store",
        "src.tender_research.document_text_extractor",
    }
    for relative in (
        "src/tender_research/rag/data_platform.py",
        "src/tender_research/rag/analysis_service.py",
        "src/tender_research/rag/prepare_service.py",
    ):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not (imported & forbidden), f"{relative}: {sorted(imported & forbidden)}"


def test_backend_neutral_search_hit_is_not_defined_by_legacy_retriever() -> None:
    root = Path(__file__).resolve().parents[2]
    adapter = (root / "src/tender_research/rag/data_platform.py").read_text(
        encoding="utf-8"
    )
    llm = (root / "src/tender_research/rag/llm.py").read_text(encoding="utf-8")
    analysis = (root / "src/tender_research/rag/analysis_service.py").read_text(
        encoding="utf-8"
    )
    assert "rag.search_types import RagSearchHit" in adapter
    assert "rag.search_types import RagSearchHit" in llm
    assert "rag.search_types import RagSearchHit" in analysis


def test_data_platform_runtime_import_graph_does_not_load_legacy_rag() -> None:
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    code = """
import sys
import src.tender_research.rag.data_platform
import src.tender_research.rag.analysis_service
import src.tender_research.rag.prepare_service

forbidden = {
    'src.tender_research.rag.chunker',
    'src.tender_research.rag.embeddings',
    'src.tender_research.rag.indexer',
    'src.tender_research.rag.retriever',
    'src.tender_research.rag.vector_store',
    'src.tender_research.document_text_extractor',
}
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise SystemExit('legacy modules loaded: ' + ', '.join(loaded))
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        check=True,
    )



def test_data_platform_is_the_default_retrieval_backend() -> None:
    from src.shared.config.settings import Settings
    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.data_platform import retrieval_backend_name

    assert TenderResearchConfig().rag_retrieval_backend == "data_platform"
    assert Settings().rag_retrieval_backend == "data_platform"

    class ConfigWithoutBackend:
        pass

    assert retrieval_backend_name(ConfigWithoutBackend()) == "data_platform"


def test_legacy_retrieval_backend_is_rejected() -> None:
    import pytest

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.data_platform import retrieval_backend_name

    config = TenderResearchConfig(rag_retrieval_backend="legacy")
    with pytest.raises(ValueError, match="legacy local RAG backend has been removed"):
        retrieval_backend_name(config)


def test_legacy_generic_rag_modules_are_removed() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "tender_research" / "rag"
    for name in ("chunker.py", "embeddings.py", "indexer.py", "retriever.py", "vector_store.py"):
        assert not (root / name).exists()

def test_generic_document_extraction_exists_only_behind_data_platform_adapter() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not (root / "src/tender_research/document_text_extractor.py").exists()

    connector = (
        root / "src/modules/tender_connectors/text_extraction.py"
    ).read_text(encoding="utf-8")
    upload = (
        root / "src/modules/tender_operator_agent_demo/upload_service_legacy.py"
    ).read_text(encoding="utf-8")
    acceptance = (
        root / "scripts/arv001/complete_corpus_contract.py"
    ).read_text(encoding="utf-8")

    for source in (connector, upload, acceptance):
        assert "process_document_bytes" in source
        assert "document_text_extractor" not in source

    forbidden_parser_markers = (
        "PdfReader",
        "word/document.xml",
        "def _extract_text_from_pdf",
        "def _extract_text_from_docx",
        "def _extract_text_from_txt",
    )
    assert not any(marker in connector for marker in forbidden_parser_markers)
