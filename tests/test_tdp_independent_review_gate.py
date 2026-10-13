"""Independent reviewing is distinct from literal LLM source quotation."""
from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.independent_review_gate import (
    assess_claims_for_independent_review,
)

SOURCE_TEXT = "Обеспечение исполнения контракта установлено в размере 10 процентов."
QUOTE = "Обеспечение исполнения контракта установлено"
FILE_ID = "FILE-01"
PURCHASE = "0372200172326000015"
RECORD = {
    "resource_id": "DP-R1",
    "document_id": "DP-D1",
    "offset_space": "data_platform_normalized_text",
}
CHUNKS = [{
    "file_id": FILE_ID,
    "resource_id": "DP-R1",
    "document_id": "DP-D1",
    "chunk_id": "DP-C1",
    "text_hash": hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
    "char_start": 0,
    "char_end": len(SOURCE_TEXT),
}]


def run(
    quote: str = QUOTE,
    *,
    notice: str | None = PURCHASE,
    chunks: list[dict] | None = None,
    source: dict | None = None,
    claims: list[dict] | None = None,
    texts: dict[str, str] | None = None,
) -> dict:
    return assess_claims_for_independent_review(
        procurement_id=PURCHASE,
        notice_purchase_number=notice,
        claims=claims if claims is not None else [
            {"file_id": FILE_ID, "exact_quote": quote, "interpretation": "GO"}
        ],
        sources_by_file={FILE_ID: RECORD if source is None else source},
        chunks=CHUNKS if chunks is None else chunks,
        chunk_text_by_id={"DP-C1": SOURCE_TEXT} if texts is None else texts,
    )


def test_exact_literal_is_proven_but_go_is_not_authorized() -> None:
    result = run()
    assert result["source_identity"] == "MATCH"
    assert result["literal_verified_count"] == 1
    assert result["claims"][0]["quote_status"] == "LITERAL_MATCH"
    assert result["claims"][0]["semantic_review"] == "PENDING_INDEPENDENT_EXPERT"
    assert result["claims"][0]["legal_review"] == "UNKNOWN"
    assert result["business_decision"] == "DEFER"
    assert result["go_eligible"] is False
    assert result["claims"][0]["evidence"]["chunk_id"] == "DP-C1"


@pytest.mark.parametrize("notice", [None, "", "0895100000126000897"])
def test_missing_or_conflicting_registry_identity_blocks_all_claims(notice: str | None) -> None:
    result = run(notice=notice)
    assert result["source_identity"] == "CONFLICT_OR_UNKNOWN"
    assert result["literal_verified_count"] == 0
    assert result["claims"][0]["evidence"] is None


def test_model_paraphrase_fake_quote_cannot_pass() -> None:
    result = run(quote="Контракт предполагает обеспечение 10 процентов.")
    assert result["claims"][0]["quote_status"] == "UNVERIFIED"


def test_wrong_chunk_hash_or_resource_cannot_pass() -> None:
    wrong = [{**CHUNKS[0], "text_hash": "0" * 64}]
    assert run(chunks=wrong)["literal_verified_count"] == 0
    assert run(source={**RECORD, "resource_id": "OTHER"})["literal_verified_count"] == 0
    assert run(texts={"DP-C1": "other"})["literal_verified_count"] == 0


def test_one_correct_and_one_wrong_claim_block_automatic_go() -> None:
    result = run(
        claims=[
            {"file_id": FILE_ID, "exact_quote": QUOTE},
            {"file_id": FILE_ID, "exact_quote": "Никаких гарантий не предусмотрено."},
        ],
    )
    assert result["claim_count"] == 2
    assert result["literal_verified_count"] == 1
    assert result["go_eligible"] is False


def test_malformed_claim_does_not_break_batch_or_promote_go() -> None:
    result = run(claims=[{}, {"file_id": "unknown", "exact_quote": QUOTE}])
    assert result["literal_verified_count"] == 0
    assert result["review_status"] == "INDEPENDENT_REVIEW_REQUIRED"
