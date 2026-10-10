"""Original-file provenance, failure safety and compatibility for TA upload assembly."""

from pathlib import Path

import pytest

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_document_collection import (
    collect_operator_documents,
    collect_operator_quote_paths,
    collect_operator_role_text,
    collect_operator_spreadsheet_sources,
)
from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)


def _collect(tmp_path: Path, metadata: dict, **overrides) -> list[AnalyzedDocument]:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    defaults = {
        "metadata": metadata,
        "input_dir": input_dir,
        "normalized_dir": tmp_path / "normalized",
        "checked_path": checked_original_input_path,
        "extract_archive": lambda path, file_id: [],
        "extract_with_provenance": lambda filename, content: (
            "Работы по восстановлению\nУказан исходный договор",
            ["review original", "review original"],
            "completed",
            object(),
        ),
        "project_source": lambda processed, *, file_id: (
            {"file_id": file_id, "resource_id": "res-real-1", "document_id": "doc-real-1"},
            [{"chunk_id": "chunk-real-1", "start_char": 0, "end_char": 22, "content_hash": "h1"}],
        ),
        "detect_role": lambda filename: "supporting",
    }
    defaults.update(overrides)
    return collect_operator_documents(**defaults)


def test_document_original_bytes_and_dp_evidence_round_trip(tmp_path: Path):
    original = b"%PDF-1.7 binary original"
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "01-original.pdf").write_bytes(original)
    metadata = {"files": [{
        "file_id": "FILE-04",
        "stored_name": "01-original.pdf",
        "display_name": "Проект контракта.pdf",
        "document_kind": "contract_draft",
        "warnings": ["preexisting", "review original"],
    }]}
    docs = _collect(tmp_path, metadata)
    assert len(docs) == 1
    assert docs[0].raw_content == original
    assert docs[0].file_id == "FILE-04"
    assert docs[0].role == "contract_draft"
    assert docs[0].text == "Работы по восстановлению\nУказан исходный договор"
    assert docs[0].evidence_chunks is metadata["files"][0]["evidence_chunks"]
    assert metadata["files"][0]["data_platform_source"] == {
        "file_id": "FILE-04", "resource_id": "res-real-1", "document_id": "doc-real-1",
    }
    assert metadata["files"][0]["evidence_chunks"] == [{
        "chunk_id": "chunk-real-1", "start_char": 0, "end_char": 22, "content_hash": "h1",
    }]
    assert metadata["files"][0]["warnings"] == ["preexisting", "review original"]
    assert (tmp_path / "normalized" / "file-04-contract_draft.txt").read_text() == docs[0].text
    assert (input_dir / "01-original.pdf").read_bytes() == original
    assert collect_operator_role_text(docs, "contract_draft") == docs[0].text
    assert collect_operator_role_text(docs, "notice") == ""


def test_unavailable_processor_never_invents_source_provenance(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "notice.txt").write_bytes(b"notice")
    metadata = {"files": [{
        "file_id": "FILE-02", "stored_name": "notice.txt",
        "display_name": "Извещение", "warnings": [],
    }]}
    docs = _collect(
        tmp_path,
        metadata,
        extract_with_provenance=lambda filename, content: (None, ["unavailable"], "failed", None),
    )
    assert docs[0].text is None
    assert docs[0].evidence_chunks is None
    assert "data_platform_source" not in metadata["files"][0]
    assert "evidence_chunks" not in metadata["files"][0]
    assert metadata["files"][0]["text_extraction_status"] == "failed"
    assert metadata["files"][0]["extracted_text_available"] is False
    assert not list((tmp_path / "normalized").iterdir())


def test_unsafe_original_path_fails_before_any_extraction(tmp_path: Path):
    invoked = []
    metadata = {"files": [{
        "file_id": "F", "stored_name": "../outside.pdf", "display_name": "bad",
    }]}
    with pytest.raises(ValueError, match="Unsafe"):
        _collect(
            tmp_path, metadata,
            extract_with_provenance=lambda *args: invoked.append(args),
        )
    assert invoked == []


def test_zip_keeps_bounded_decoder_results_and_single_warning(tmp_path: Path):
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "safe.zip").write_bytes(b"zip")
    doc = AnalyzedDocument(
        display_name="nested.pdf", extension=".pdf", role="technical_spec",
        text="Спецификация", extracted_text_available=True, warnings=[],
        source="upload", file_id="FILE-9:1",
    )
    metadata = {"files": [{
        "file_id": "FILE-9", "stored_name": "safe.zip",
        "display_name": "archive", "warnings": ["other"],
    }]}
    docs = _collect(
        tmp_path,
        metadata,
        extract_archive=lambda path, file_id: [doc],
        extract_with_provenance=lambda *args: pytest.fail("ZIP cannot be decoded as a regular file"),
    )
    assert docs == [doc]
    assert metadata["files"][0]["warnings"] == ["other", "ZIP archive inspected in safe local mode."]
    assert "data_platform_source" not in metadata["files"][0]


def test_quote_paths_and_spreadsheets_are_source_preserving(tmp_path: Path):
    original = tmp_path / "quote.xlsx"
    original.write_bytes(b"sheet bytes")
    meta = {"files": [{"stored_name": "quote.xlsx"}]}
    quote_paths = collect_operator_quote_paths(
        metadata=meta, input_dir=tmp_path,
        checked_path=checked_original_input_path,
        detect_role=lambda name: "tkp",
    )
    assert quote_paths == [original.resolve()]
    doc = AnalyzedDocument(
        display_name="КП.xlsx", extension=".xlsx", role="tkp",
        text=None, extracted_text_available=False, warnings=[],
        source="upload", file_id="FILE-10", raw_content=b"sheet bytes",
    )
    [source] = collect_operator_spreadsheet_sources([doc])
    assert source.file_id == doc.file_id
    assert source.raw_content == doc.raw_content
    assert source.display_name == doc.display_name
    assert source.role_hint == "tkp"


def test_legacy_role_and_sheet_facade_preserved():
    doc = AnalyzedDocument(
        display_name="ТЗ.xlsx", extension=".xlsx", role="technical_spec",
        text="Данные", extracted_text_available=True, warnings=[],
        source="upload", file_id="FILE-1", raw_content=b"original",
    )
    assert legacy._collect_role_text([doc], "technical_spec") == "Данные"
    assert legacy._collect_spreadsheet_sources([doc]) == collect_operator_spreadsheet_sources([doc])
