"""Do not convert literal archived source topics into a legal bid decision."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from scripts.acceptance.build_r4_competitive_semantic_audit import build_review
from src.modules.tender_operator_agent_demo.r4_material_condition_triage import (
    all_topic_occurrences,
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

def test_all_mentions_are_not_silently_reduced_to_first_source_hit():
    text = (
        "PARAGRAPH-0001: Обеспечение исполнения контракта не требуется.\n"
        "PARAGRAPH-0002: Обеспечение исполнения контракта составляет 10 процентов.\n"
        "PARAGRAPH-0003: Предмет исполнения не касается иных обеспечений."
    )
    first = literal_candidates(text)
    all_hits = all_topic_occurrences(text)
    matching = [v for v in all_hits if v["review_topic"] == "Обеспечение заявки/контракта"]
    assert len([v for v in first if v["review_topic"] == "Обеспечение заявки/контракта"]) == 1
    assert len(matching) == 2
    assert matching[0]["literal_start"] < matching[1]["literal_start"]
    assert matching[1]["source_locator"] == "PARAGRAPH-0002"
    assert matching[0]["context_flag"] == "NEGATION_CUE_NEAR_MENTION"
    assert matching[1]["context_flag"] != "NEGATION_CUE_NEAR_MENTION"
    assert all(v["review_status"] == "LEXICAL_HIT_NOT_LEGAL_OBLIGATION" for v in matching)


def test_repeated_keyword_hits_keep_sha_bound_offsets_and_separate_table_locators():
    text = (
        "TABLE-001 ROW-001 CELL-001: Персональные данные.\n"
        "TABLE-001 ROW-002 CELL-001: Персональные данные.\n"
        "PARAGRAPH-0010: персональные данные"
    )
    hits = [v for v in all_topic_occurrences(text)
            if v["review_topic"] == "Персональные данные и ИБ"]
    assert len(hits) == 3
    assert [v["source_locator"] for v in hits] == [
        "TABLE-001 ROW-001 CELL-001",
        "TABLE-001 ROW-002 CELL-001",
        "PARAGRAPH-0010",
    ]
    assert len({v["literal_start"] for v in hits}) == 3
    assert all(v["source_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
               for v in hits)


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
    full = audit["all_topic_mentions_scan"]
    assert full["text_units"] == 97
    assert full["original_attachments"] == 96
    assert full["total_pattern_occurrences"] == 2030
    assert full["first_only_prior_coverage"] == 265
    assert full["additional_pattern_occurrences"] == 1765
    assert len(full["second_source_hit_per_topic"]) == 217
    assert len(full["one_additional_original_locator_per_case"]) == 20
    roles = full["license_context_role_clarifications"]
    assert len(roles) == 5
    assert sum(v["source_role"] == "ISSUING_BANK_LICENSE_NOT_PARTICIPANT_LICENSE"
               for v in roles) == 3
    assert sum(v["source_role"] == "DELIVERED_SOFTWARE_LICENSE_TERMS_NOT_PARTICIPANT_LICENSE"
               for v in roles) == 1
    assert sum(v["source_role"] == "CONTRACTOR_LICENSE_WORDING_REQUIRES_LEGAL_REVIEW"
               for v in roles) == 1
    assert all(not v["participant_eligibility_approved"] and not v["expert_signed"]
               and not v["bid_ready"] for v in roles)

    assert len({v["registry_number"] for v in
                full["one_additional_original_locator_per_case"]}) == 20
    assert sum(c["all_pattern_occurrences"] for c in audit["cases"]) == 2030
    assert all(not v["bid_ready"] and not v["human_signed"]
               for v in full["one_additional_original_locator_per_case"])

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
