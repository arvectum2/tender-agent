"""Expert-review packet prefill cannot invent human gold or release."""
from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.expert_source_review_packet import (
    build_expert_source_review_packet,
)
from src.modules.tender_operator_agent_demo.full_corpus_research import research_full_corpus
from src.modules.tender_operator_agent_demo.source_claim_proof import (
    audit_model_eis_summary,
    bind_source_span,
)


def doc(fid: str, role: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(file_id=fid, role=role, display_name=fid + ".txt", text=text)


def source_xml() -> str:
    return (
        "<export><purchaseNumber>0372200172326000015</purchaseNumber>"
        "<maxPrice>1000000.00</maxPrice>"
        "<endDT>2026-10-16T10:00:00+03:00</endDT>"
        "<publishDTInEIS>2026-10-08T10:53:46+03:00</publishDTInEIS>"
        "</export>"
    )


def test_machine_source_prefill_does_not_masquerade_as_approved_legal_gold():
    notice = doc("FILE-01", "notice", source_xml())
    contract = doc("FILE-02", "contract_draft",
                   "3.8. По соглашению сторон допускается изменение объема услуг и цены контракта.")
    originals = [notice, contract]
    research = research_full_corpus(originals)
    quotes = []
    for theme in research["findings"]:
        for hit in theme["hits"][:1]:
            proof = bind_source_span(
                originals, research, file_id=hit["file_id"],
                start=hit["start"], end=hit["end"], quote=hit["quote"],
                expected_text_sha256=hit["source_sha256"],
            )
            quotes.append({**proof, "theme": theme["key"]})
    typed = audit_model_eis_summary(
        research, {"tender_summary": "NMCK: 1,000,000.00 RUB; "
                                     "Submission deadline: 16.10.2026 10:00:00 +03:00"},
    )
    packet = build_expert_source_review_packet(
        research, quote_proofs=quotes, typed_eis_claims=typed,
        quality_gate={"status": "SEMANTIC_REVIEW_REQUIRED"},
    )
    assert packet["registry_number_from_original_only"] == "0372200172326000015"
    assert packet["source_proof_count"] > 0
    assert len(packet["case_source_manifest_sha256"]) == 64
    assert packet["human_reviews_completed"] == 0
    assert packet["human_gold_attested"] is False
    assert packet["expert_signature_present"] is False
    assert packet["arv001_release_gate"] == "NOT_READY"
    assert packet["bid_ready"] is False
    assert "CURRENT_OFFICIAL_REVISION_NOT_OWNER_ATTESTED" in packet["unresolved_reasons"]
    assert "NO_INDEPENDENT_HUMAN_GOLD_REVIEW" in packet["unresolved_reasons"]
    assert len(packet["rubric"]) >= 14
    for item in packet["rubric"]:
        assert item["human_label"] is None
        assert item["human_reviewer_id"] is None
        assert item["needs_independent_review"] is True


def test_unsupported_223_fz_and_b2b_procedures_are_not_auto_attested():
    for text in (
        "223-ФЗ конкурентная закупка ПО с рассмотрением заявок.",
        "Коммерческая закупка на разработку портала, 900000 рублей.",
    ):
        research = research_full_corpus([doc("x", "supporting", text)])
        packet = build_expert_source_review_packet(research)
        assert packet["registry_number_from_original_only"] is None
        assert packet["source_quality_gate_status"] == "NOT_EVALUATED"
        assert "NO_UNIQUE_SOURCE_REGISTRY_NUMBER" in packet["unresolved_reasons"]
        assert "NO_SHA_EXACT_SOURCE_PROOF" in packet["unresolved_reasons"]
        assert packet["arv001_release_gate"] == "NOT_READY"
        assert packet["human_reviews_completed"] == 0


def test_conflicting_versions_and_unread_original_block_review_package():
    originals = [
        doc("a", "notice", source_xml()),
        doc("b", "notice", source_xml().replace("1000000.00", "900000.00")),
        doc("c", "technical_spec", ""),
    ]
    research = research_full_corpus(originals)
    packet = build_expert_source_review_packet(research)
    assert "ORIGINAL_DOCUMENTS_INCOMPLETE" in packet["unresolved_reasons"]
    assert "MULTIPLE_OFFICIAL_NOTICE_REVISIONS" in packet["unresolved_reasons"]
    assert packet["source_inventory"][2]["extraction_status"] == "UNEXTRACTED"
    assert packet["bid_ready"] is False


def test_tampered_source_and_model_conflict_are_visible_but_never_human_labels():
    xml = source_xml()
    research = research_full_corpus(
        [doc("x", "notice", xml)],
        manifest=[{"file_id": "x", "text_sha256": "0" * 64}],
    )
    packet = build_expert_source_review_packet(
        research,
        quote_proofs=[{"file_id":"x","status":"SOURCE_SPAN_UNVERIFIED"}],
        typed_eis_claims={"contradictions_count": 1, "unmentioned_archived_eis_fields":["nmck"]},
        source_modality_audit={"contradiction_count": 2},
        quality_gate={"status": "CORPUS_INCOMPLETE"},
    )
    assert packet["source_quality_gate_status"] == "CORPUS_INCOMPLETE"
    assert packet["material_claim_contradictions"] == 3
    assert "SOME_SOURCE_QUOTES_UNVERIFIED" in packet["unresolved_reasons"]
    assert "MODEL_SOURCE_CONTRADICTION" in packet["unresolved_reasons"]
    assert "MODEL_MISSED_SOURCE_FIELDS" in packet["unresolved_reasons"]
    assert packet["human_gold_attested"] is False


def test_source_manifest_hash_deterministic_and_independent_of_input_order():
    docs = [doc("A", "technical_spec", "ТЗ: сайт."), doc("B", "notice", "Номер закупки 123")]
    left = build_expert_source_review_packet(research_full_corpus(docs))
    right = build_expert_source_review_packet(research_full_corpus(docs[::-1]))
    assert left["case_source_manifest_sha256"] == right["case_source_manifest_sha256"]
    assert left["source_inventory"] == right["source_inventory"]
