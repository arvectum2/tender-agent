"""R4 verified 20-competitive + 4-negative original bytes and model quote gates."""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_official_competitive_cohort import (
    validate_cohort,
    verify_original_notice,
)
from src.modules.tender_operator_agent_demo.r4_original_claim_audit import (
    verify_saved_quote,
)
from scripts.acceptance.build_r4_competitive_semantic_audit import (
    build_review,
    readable_review,
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _original_archive(tmp_path: Path):
    n = "0372200172326000015"
    typ = "epNotificationEZK2020"
    xml = (
        '<export xmlns="http://zakupki.gov.ru/oos/export/1">'
        f'<{typ}><id>{n}</id></{typ}></export>'
    ).encode()
    archive = tmp_path / "documentation-archive.zip"
    filename = f"{typ}_{n}_1_TEST.xml"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(filename, xml)
    meta = {
        "reg_number": n, "zip_sha256": _sha(archive.read_bytes()),
        "notice": {
            "xml_member": filename, "source_xml_sha256": _sha(xml),
            "type_xml": typ, "method": "COMPETITIVE_ELECTRONIC_QUOTATIONS",
            "version": 1, "archived_submission_endDT": "2026-10-16T10:00:00+03:00",
            "source_purchase_object": "Сайт музея хлеба",
        },
    }
    return archive, meta


def test_single_typed_original_export_and_archived_source_provenance(tmp_path):
    archive, meta = _original_archive(tmp_path)
    verified = verify_original_notice(meta, archive)
    assert verified["registry_number"] == meta["reg_number"]
    assert verified["notice_type"] == "epNotificationEZK2020"
    assert verified["archive_xml_files"] == 1
    assert verified["archived_submission_end"] == "2026-10-16T10:00:00+03:00"
    assert verified["bid_ready"] is False
    assert verified["current_eis_attested"] is False


def test_archived_original_source_bytes_and_notice_root_must_not_drift(tmp_path):
    archive, meta = _original_archive(tmp_path)
    wrong = json.loads(json.dumps(meta))
    wrong["zip_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="ZIP bytes SHA"):
        verify_original_notice(wrong, archive)
    wrong = json.loads(json.dumps(meta))
    wrong["notice"]["source_xml_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="XML SHA"):
        verify_original_notice(wrong, archive)
    wrong = json.loads(json.dumps(meta))
    wrong["notice"]["type_xml"] = "epNotificationEF2020"
    with pytest.raises(ValueError, match="typed notice"):
        verify_original_notice(wrong, archive)


def test_ambiguous_multiple_official_notices_are_not_accepted(tmp_path):
    archive, meta = _original_archive(tmp_path)
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr(meta["notice"]["xml_member"], b"<fake/>")
    meta["zip_sha256"] = _sha(archive.read_bytes())
    with pytest.raises(ValueError, match="ambiguous"):
        verify_original_notice(meta, archive)


def test_original_binary_sha_and_quote_literal_and_layout_not_semantic_go(tmp_path):
    folder = tmp_path / "toa-run-20261014-test"
    (folder / "normalized").mkdir(parents=True)
    (folder / "input").mkdir()
    source = "file-07-contract_draft.txt"
    text = "Обеспечение исполнения договора составляет 5 процентов."
    b = text.encode()
    (folder / "normalized" / source).write_bytes(b)
    binary = b"ORIGINAL-DOCX-DATA"
    (folder / "input" / "original.docx").write_bytes(binary)
    (folder / "metadata.json").write_text(
        json.dumps({"files": [{"file_id": "FILE-07", "stored_name": "original.docx"}]})
    )
    valid = (_sha(binary), len(binary))
    exact = verify_saved_quote(folder, source, "5 процентов", _sha(b), {valid})
    assert exact["literal_quote"] is True
    assert exact["original_bytes"] is True
    assert exact["legal_interpretation_approved"] is False
    damaged = verify_saved_quote(folder, source, "5 процентов", "f" * 64, {valid})
    assert damaged["status"] == "SOURCE_TEXT_SHA_MISMATCH"
    unsupported = verify_saved_quote(folder, source, "10 процентов", _sha(b), {valid})
    assert unsupported["status"] == "QUOTE_NOT_SUPPORTED_AS_LIVE_QUOTATION"
    unattested = verify_saved_quote(folder, source, "5 процентов", _sha(b), set())
    assert unattested["status"] == "QUOTE_MATCH_ONLY_SAVED_TEXT"


def test_historical_canonical_twenty_has_four_noncompetitors_and_one_reserve():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("original EIS private archived selection absent on GitHub runner")
    source = Path(root)
    data = json.loads(
        (source / "ai-expert-20261012/positive-eis-replacements-20261012/"
         "verified-competitive-20-plus-four-negative.json").read_text()
    )
    assert validate_cohort(data)["competitive"] == 20
    assert {v["noncompetitive_reason"] for v in data["negative_cases"]} == {
        "MARKET_RESEARCH_PRICE_INFORMATION_REQUEST",
        "SPECIAL_SINGLE_SUPPLIER_NOT_REGULAR_COMPETITIVE_TENDER",
    }
    data["positive_cases"][0]["notice"]["method"] = "NONCOMPETITIVE_SINGLE_SUPPLIER_ART93_12"
    with pytest.raises(ValueError, match="competitive"):
        validate_cohort(data)


def test_official_all_twenty_and_llm_original_claims_private_offline(tmp_path):
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("original EIS private archived selection absent on GitHub runner")
    result = build_review(Path(root))
    assert len(result["competitive_notices"]) == 20
    assert len(result["negative_controls"]) == 4
    assert result["official_source_verified"] == 21
    assert result["saved_model_claims"]["saved_runs"] == 10
    assert result["saved_model_claims"]["claims"] == 26
    assert result["saved_model_claims"]["literal_official_originals"] == 22
    assert result["saved_model_claims"]["whitespace_variant_official_originals"] == 3
    assert result["saved_model_claims"]["unsubstantiated_literal_quotes"] == 1
    new = result["additional_four_cases_and_21_original_binaries"]
    assert new["original_binaries_sha_verified"] == 21
    assert new["normalized_texts_sha_verified"] == 22
    assert new["model_claims_checked"] == 21
    assert new["model_claims_exact_source_quotes"] == 20
    assert new["claims_requiring_quote_correction"] == 1
    assert new["model_batches_exceeding_claim_count_cap"] == 3
    assert result["all_saved_model_claims_checked"] == 47
    assert result["bid_ready"] is False
    assert result["human_gold_review_signed"] == 0
    text = readable_review(result)
    assert text.count("Открытый конкурс") == 2
    assert "0376300000126000193" in text
    assert "0162200011826003089" in text
    for value in ("no_data", "getDocsIP", "Traceback", "HTTP 409"):
        assert value not in text
    (tmp_path / "test-user-report.md").write_text(text)
