import hashlib
from pathlib import Path

from src.modules.market_intelligence.pq_chatgpt_review import prepare_packet


def test_mislabeled_rtf_as_docx_is_preserved_without_fabricated_text(tmp_path: Path):
    originals = tmp_path / "32616339168"
    originals.mkdir()
    content = b"{\\rtf1\\ulc1 not-a-valid-DOCX-package}"
    file = originals / "mislabeled.docx"
    file.write_bytes(content)
    ontology = tmp_path / "ontology.yaml"
    ontology.write_text("families:\n  - id: ukrm\n    positive:\n      - УКРМ\n")
    packet = prepare_packet(
        document_dir=originals, ontology_path=ontology,
        registry_number="32616339168")
    item = packet["documents"][0]
    assert item["sha256"] == hashlib.sha256(content).hexdigest()
    assert item["method"] == "invalid_office_archive_container"
    assert item["text"] == ""
    assert item["lexical_hints_only"] == []
    assert packet["extraction_errors"][0]["error_type"] == "BadZipFile"
    assert packet["market_total_rub"] is None
