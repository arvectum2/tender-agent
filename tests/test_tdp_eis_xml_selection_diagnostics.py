"""Operator must explain why original-EIS facts are UNKNOWN without guessing."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo import (
    operator_workspace_evidence as evidence,
)
from tests.test_apr03b_source_evidence import GOOD_XML


def test_competing_xml_revisions_produce_explicit_reason(source):
    directory, metadata = source
    (directory / "another.xml").write_text(
        GOOD_XML.replace("<maxPrice>1000000.00", "<maxPrice>1200000.00")
    )
    metadata["files"].append({
        "stored_name": "another.xml",
        "extension": ".xml",
        "file_id": "FILE-02",
        "display_name": "another.xml",
    })
    result = evidence.get_operator_source_evidence("test")
    assert result["source_selection"] == "ambiguous_notice_revisions"
    assert result["source_candidate_count"] == 2
    assert all(f["status"] == "UNKNOWN" for f in result["facts"].values())
    assert any("несколько" in message.lower() for message in result["warnings"])


def test_wrong_registry_has_distinct_selection_reason(source):
    _directory, metadata = source
    metadata["procurement_id"] = "1111111111111111111"
    result = evidence.get_operator_source_evidence("test")
    assert result["source_selection"] == "no_unique_registry_matched_xml"
    assert result["source_candidate_count"] == 0
    assert all(f["status"] == "UNKNOWN" for f in result["facts"].values())


def test_single_source_preserves_existing_facts(source):
    result = evidence.get_operator_source_evidence("test")
    assert result["source_selection"] == "single_registry_matched_xml"
    assert result["source_candidate_count"] == 1
    assert all(f["status"] == "KNOWN" for f in result["facts"].values())


def test_223_source_stays_unsupported_even_with_xml(source):
    _directory, metadata = source
    metadata["procurement_source"] = "public_eis_html_223fz"
    result = evidence.get_operator_source_evidence("test")
    assert result["source_selection"] == "unsupported_source"
    assert result["source_candidate_count"] == 0
    assert all(f["status"] == "UNKNOWN" for f in result["facts"].values())


@pytest.fixture
def source(tmp_path, monkeypatch):
    directory = tmp_path / "run" / "input"
    directory.mkdir(parents=True)
    (directory / "notice.xml").write_text(GOOD_XML, encoding="utf-8")
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "procurement_id": "0372200172326000015",
        "files": [{
            "file_id": "FILE-01",
            "stored_name": "notice.xml",
            "display_name": "original.xml",
            "extension": ".xml",
        }],
    }
    monkeypatch.setattr(evidence, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(evidence, "get_demo_run_input_dir", lambda _: directory)
    return directory, metadata
