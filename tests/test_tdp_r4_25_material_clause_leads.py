"""No material legal assertion without exact original SHA and literal clause locator."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import (
    r4_new_original_material_leads as leads,
)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _fixture(tmp_path: Path, monkeypatch) -> Path:
    grouped = {}
    for number, slot, quote, *_ in leads.LEADS:
        grouped.setdefault((number, slot), []).append(quote)
    data = []
    for (number, slot), quotes in grouped.items():
        filename = slot + ".docx.text-private.txt"
        body = "\n".join(f"PARAGRAPH-{i+1:04d}: {q}" for i, q in enumerate(quotes)) + "\n"
        folder = tmp_path / number
        folder.mkdir(exist_ok=True)
        (folder / filename).write_text(body, encoding="utf8")
        data.append({
            "registry_number": number, "text_private_file": filename,
            "text_status": "TEXT_EXTRACTED", "text_sha256": _sha(body.encode()),
            "origin_sha256": "a" * 64, "text_chars": len(body),
            "source_name": "Оригинал ТЗ.docx",
        })
    for i in range(18):
        n = f"{i+1:019d}"
        filename = "attachment-01.docx.text-private.txt"
        body = "PARAGRAPH-0001: Исходная документация.\n"
        folder = tmp_path / n
        folder.mkdir()
        (folder / filename).write_text(body, encoding="utf8")
        data.append({
            "registry_number": n, "text_private_file": filename,
            "text_status": "TEXT_EXTRACTED", "text_sha256": _sha(body.encode()),
            "origin_sha256": "b" * 64, "text_chars": len(body),
            "source_name": "Исходный файл.docx",
        })
    assert len(data) == 25
    payload = json.dumps(data, ensure_ascii=False).encode()
    (tmp_path / "text-extraction-private-receipt.json").write_bytes(payload)
    monkeypatch.setattr(leads, "RECEIPT_SHA256", _sha(payload))
    return tmp_path


def test_located_original_material_leads_are_not_signed_go(tmp_path, monkeypatch):
    root = _fixture(tmp_path, monkeypatch)
    result = leads.verify_material_clause_leads(root)
    assert result["source_original_attachments_with_text"] == 25
    assert result["independently_located_clause_leads"] == 12
    assert result["procurements_with_early_clause_leads"] == 7
    assert result["full_contract_semantic_reviews_signed"] == 0
    assert result["bid_ready"] is False
    for condition in result["leads"]:
        assert condition["evidence_locator"].startswith("PARAGRAPH-")
        assert condition["literal_quote"]
        assert condition["character_offset"] >= 0
        assert condition["interpretation_status"].startswith("REQUIRES_")
        assert condition["human_signed"] is False


def test_modified_original_extracted_text_is_rejected(tmp_path, monkeypatch):
    root = _fixture(tmp_path, monkeypatch)
    number, slot, *_ = leads.LEADS[0]
    file = root / number / (slot + ".docx.text-private.txt")
    file.write_text(file.read_text() + " изменено", encoding="utf8")
    with pytest.raises(ValueError, match="receipt mismatch"):
        leads.verify_material_clause_leads(root)


def test_original_clause_without_literal_source_fails_closed(tmp_path, monkeypatch):
    root = _fixture(tmp_path, monkeypatch)
    number, slot, quote, *_ = leads.LEADS[0]
    file = root / number / (slot + ".docx.text-private.txt")
    body = file.read_text().replace(quote, "утверждение модели без подтверждения")
    file.write_text(body)
    receipt = root / "text-extraction-private-receipt.json"
    records = json.loads(receipt.read_text())
    for entry in records:
        if entry["registry_number"] == number and entry["text_private_file"].startswith(slot):
            entry["text_chars"] = len(body)
            entry["text_sha256"] = _sha(body.encode())
    payload = json.dumps(records, ensure_ascii=False).encode()
    receipt.write_bytes(payload)
    monkeypatch.setattr(leads, "RECEIPT_SHA256", _sha(payload))
    with pytest.raises(ValueError, match="clause missing"):
        leads.verify_material_clause_leads(root)


def test_private_25_original_clause_evidence_replay_if_connected():
    source = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not source:
        pytest.skip("private original evidence is not distributed to GitHub CI")
    path = (Path(source) / "ai-expert-20261012" /
            "competitive-25-original-text-20261014")
    proof = leads.verify_material_clause_leads(path)
    assert proof["independently_located_clause_leads"] == 12
    assert proof["source_original_attachments_with_text"] == 25
    assert proof["full_contract_semantic_reviews_signed"] == 0


def test_clause_must_be_tied_to_same_official_notice_and_binary_sha(tmp_path, monkeypatch):
    root = _fixture(tmp_path, monkeypatch)
    extraction = leads.verify_material_clause_leads(root)
    cases = {}
    for item in extraction["leads"]:
        case = cases.setdefault(item["registry_number"], {
            "registry_number": item["registry_number"], "documents": [],
        })
        record = {
            "original_filename": item["original_document_name"],
            "original_document_sha256": item["original_binary_sha256"],
        }
        if record not in case["documents"]:
            case["documents"].append(record)
    # The remaining original cases remain in the archive, but are not sampled.
    for i in range(13):
        n = f"{i+1000:019d}"
        cases[n] = {"registry_number": n, "documents": []}
    coverage = {"source_shas_attested": 96, "cases": list(cases.values())}
    assert leads.validate_clause_leads_against_official_attachments(
        extraction, coverage
    )["original_binary_sha_and_notice_edition_links_verified"] == 12
    coverage["cases"][0]["documents"][0]["original_document_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="not attested"):
        leads.validate_clause_leads_against_official_attachments(extraction, coverage)
