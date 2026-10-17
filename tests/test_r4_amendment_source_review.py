"""Live EIS binary/notice pins and source-only amendment reviewer verification."""
from __future__ import annotations

import copy
import json
import os
import zipfile
from pathlib import Path

import pytest

from scripts.acceptance.build_r4_amendment_clause_review import (
    human_report,
    source_attested_revision,
    verified_document_text,
)


def private_bound():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("First-party original evidence only mounted on Mac mini")
    base = Path(root)
    private = (
        base / "ai-expert-20261014" / "v4-material-amendment-review"
        / "source-verified-old-new-pairs-private.json"
    )
    if not private.exists():
        pytest.skip("Private source-to-revision pair receipt absent")
    data = Path("docs/acceptance/data")
    return (
        base, json.loads(private.read_text()),
        json.loads((data / "TDP_R4_20_TRUE_COMPETITIVE_ORIGINAL_SEMANTIC_AUDIT_2026-10-14.json").read_text()),
        json.loads((data / "TDP_R4_20_OFFICIAL_CURRENT_XML_FRESHNESS_2026-10-14.json").read_text()),
    )


def replay(**overrides):
    root, pairs, prior, current = private_bound()
    params = {
        "original_eis_inventory": prior, "current_eis_inventory": current,
        "notice_number": "0348100024426000039",
    } | overrides
    return source_attested_revision(root, pairs, **params)


def test_three_original_pairs_attested_and_only_tz_has_keyword_delta():
    result = replay()
    assert result["paired_distinct_originals"] == 3 and not result["bid_ready"]
    indexed = {x["source_pair_label"]: x for x in result["pairs"]}
    assert indexed["Основной проект контракта"]["textual_sequence_similarity"] == 1
    assert indexed["Основной проект контракта"]["changed_new_text_topical_leads"] == []
    assert indexed["Описание объекта закупки — ТЗ"]["textual_sequence_similarity"] < 0.9
    assert indexed["Приложение ПИК к контракту"]["textual_sequence_similarity"] > 0.95
    topics = {x["topic"] for x in indexed["Описание объекта закупки — ТЗ"]["changed_new_text_topical_leads"]}
    assert {"Гарантийные обязательства", "Приёмка результата"} <= topics
    report = human_report(result)
    assert "не правовое заключение" not in report.lower() or "не является" in report.lower()
    assert "bid_ready=false" in report


def test_unpinned_previous_or_current_original_rejected():
    root, pairs, prior, current = private_bound()
    bad = copy.deepcopy(pairs)
    bad[0]["previous_original_binary_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="Historic original"):
        source_attested_revision(
            root, bad, original_eis_inventory=prior,
            current_eis_inventory=current, notice_number="0348100024426000039",
        )
    bad = copy.deepcopy(pairs)
    bad[0]["current_original_binary_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="Current original"):
        source_attested_revision(
            root, bad, original_eis_inventory=prior,
            current_eis_inventory=current, notice_number="0348100024426000039",
        )
    bad = copy.deepcopy(pairs)
    bad[0]["previous_extracted_text_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="SHA"):
        source_attested_revision(
            root, bad, original_eis_inventory=prior,
            current_eis_inventory=current, notice_number="0348100024426000039",
        )


def test_untrusted_archive_and_unknown_binary_format_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        verified_document_text(b"nothing", "exe.run")
    with pytest.raises(zipfile.BadZipFile):
        verified_document_text(b"not a ZIP archive", "unexpected.zip")
