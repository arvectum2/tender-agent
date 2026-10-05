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
