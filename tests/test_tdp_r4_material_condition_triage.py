"""Do not convert literal archived source topics into a legal bid decision."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.acceptance.build_r4_competitive_semantic_audit import build_review
from src.modules.tender_operator_agent_demo.r4_material_condition_triage import (
    literal_candidates,
    source_bound_triage,
)


def test_literal_topic_has_real_offset_and_source_locator():
    text = "PARAGRAPH-0012: Проект контракта.\nPARAGRAPH-0013: Обеспечение исполнения контракта указано в договоре."
    leads = literal_candidates(text)
    assert any(
        c["review_topic"] == "Обеспечение заявки/контракта"
        and c["source_locator"] == "PARAGRAPH-0013"
        and text[c["literal_start"]:].startswith(c["literal_text"])
        and c["review_status"] == "LITERAL_SIGNAL_NOT_LEGAL_INTERPRETATION"
        for c in leads
    )


def test_negated_requirement_must_not_be_promoted_to_legal_conclusion():
    leads = literal_candidates("Обеспечение исполнения контракта НЕ требуется.")
    assert leads and all("legal_conclusion" not in item for item in leads)


def test_empty_or_incomplete_source_manifest_fails_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="complete original EIS"):
        source_bound_triage(tmp_path, {"cases": [], "source_shas_attested": 0})


def test_all_96_actual_originals_remain_non_decisional_when_present():
    root = os.getenv("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("original EIS archive is private, unavailable in public CI")
    report = build_review(Path(root))
    audit = report["all_original_material_condition_triage"]
    assert audit["original_attachments_with_source_matched_text"] == 96
    assert audit["source_text_units_read"] == 97
    assert len(audit["cases"]) == 20
    assert sum(case["source_documents_read"] for case in audit["cases"]) == 96
    assert len(audit["source_bound_literal_leads"]) == 265
    assert all(len(c["top_review_topics"]) <= 3 for c in audit["cases"])
    assert audit["human_signed_full_semantic_reviews"] == 0
    assert audit["bid_ready"] is False
    assert all(x["expert_signed"] is False and not x["bid_ready"]
               for x in audit["source_bound_literal_leads"])
