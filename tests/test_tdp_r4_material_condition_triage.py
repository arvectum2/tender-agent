"""Do not convert literal archived source topics into a legal bid decision."""
from __future__ import annotations

import hashlib
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
    assert leads[0]["context_flag"] == "NEGATION_CUE_NEAR_MENTION"



def test_context_attests_exact_hash_but_does_not_publish_full_clause():
    text = ("PARAGRAPH-0001: Участник обязан предоставить лицензионный договор "
            "при наличии требуемого программного обеспечения.")
    item = next(i for i in literal_candidates(text)
                if i["review_topic"] == "Права на ПО и результаты")
    assert item["source_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert text[item["context_start"]:item["context_end"]].encode()
    assert item["context_sha256"] == hashlib.sha256(
        text[item["context_start"]:item["context_end"]].encode()
    ).hexdigest()
    assert item["context_flag"] == "OBLIGATION_VERB_NEAR_MENTION"
    assert "context_text" not in item
    assert item["review_status"] == "LITERAL_SIGNAL_NOT_LEGAL_INTERPRETATION"


def test_negation_in_previous_sentence_does_not_cancel_next_obligation():
    text = ("Личное присутствие не требуется. "
            "Сдача и приемка результатов оформляются отдельным актом.")
    leads = literal_candidates(text)
    acceptance = next(x for x in leads if x["review_topic"] == "Приёмка результата")
    assert acceptance["context_flag"] != "NEGATION_CUE_NEAR_MENTION"
    assert acceptance["review_status"] == "LITERAL_SIGNAL_NOT_LEGAL_INTERPRETATION"


def test_heading_or_label_is_not_interpreted_as_obligation():
    item = literal_candidates("Обеспечение исполнения контракта")[0]
    assert item["context_flag"] == "POSSIBLE_HEADING_OR_TABLE_LABEL"
    assert item["review_status"] == "LITERAL_SIGNAL_NOT_LEGAL_INTERPRETATION"

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
    assert sum(audit["context_flag_totals"].values()) == 265
    assert all(
        x["source_text_sha256"] and x["context_sha256"]
        and x["context_start"] <= x["literal_start"] < x["context_end"]
        for x in audit["source_bound_literal_leads"]
    )
    assert audit["context_flag_totals"]["NEGATION_CUE_NEAR_MENTION"] == 3
    examples = audit["manually_rechecked_archival_nonrequirement_wording"]
    assert len(examples) == 3
    assert all(e["original_binary_sha256"] and e["source_locator"]
               and not e["legal_interpretation_signed"] and not e["bid_ready"]
               for e in examples)
    assert sum(c["negation_cue_leads"] for c in audit["cases"]) == audit[
        "context_flag_totals"
    ].get("NEGATION_CUE_NEAR_MENTION", 0)
    assert all(len(c["top_review_topics"]) <= 3 for c in audit["cases"])
    assert audit["human_signed_full_semantic_reviews"] == 0
    assert audit["bid_ready"] is False
    assert all(x["expert_signed"] is False and not x["bid_ready"]
               for x in audit["source_bound_literal_leads"])
