from src.modules.tender_operator_agent_demo.semantic_expert_review import (
    review_model_claims,
)

CASE = "0372200172326000015"
CLAIM = {
    "source_identity": "MATCH",
    "evidence_id": "dp-chunk-1:12:42",
    "exact_quote": "Обеспечение составляет 10 процентов",
    "interpretation": "Требуется обеспечение в 10 процентов",
}


def verify(*, reviewer=None, claims=None, notice=CASE):
    return review_model_claims(
        procurement_id=CASE,
        notice_purchase_number=notice,
        claims=[CLAIM] if claims is None else claims,
        reviewer=reviewer,
    )


def test_unavailable_reviewer_is_not_fake_expert_success():
    result = verify()
    assert result["reason"] == "INDEPENDENT_REVIEWER_UNAVAILABLE"
    assert result["reviewer_invoked"] is False
    assert result["go_eligible"] is False


def test_unverified_quote_and_registry_mismatch_block_invocation():
    def unexpected(_):
        raise AssertionError("reviewer must not be called")

    assert verify(notice="0895100000126000897", reviewer=unexpected)["reviewer_invoked"] is False
    assert verify(claims=[{**CLAIM, "source_identity": "UNKNOWN"}], reviewer=unexpected)["reason"] == "UNVERIFIED_SOURCE_EVIDENCE"
    assert verify(claims=[], reviewer=unexpected)["reason"] == "NO_VERIFIABLE_CLAIMS"


def test_separate_expert_supported_does_not_authorize_go():
    r = verify(reviewer=lambda _: {
        "verdicts": [{"evidence_id": CLAIM["evidence_id"], "decision": "SUPPORTED", "reason": "Смысл ограничен исходной цитатой"}]
    })
    assert r["reviewer_invoked"] is True
    assert r["semantic_status"] == "EXPERT_SOURCE_CLAIMS_SUPPORTED"
    assert r["business_decision"] == "DEFER"
    assert r["go_eligible"] is False


def test_semantic_overclaim_rejected_even_with_literal_quote():
    r = verify(reviewer=lambda _: {
        "verdicts": [{"evidence_id": CLAIM["evidence_id"], "decision": "CONTRADICTED", "reason": "Буквальная цитата не подтверждает категоричное толкование"}]
    })
    assert r["semantic_status"] == "EXPERT_REVIEW_HAS_FINDINGS"
    assert r["claims"][0]["decision"] == "CONTRADICTED"
    assert r["go_eligible"] is False


def test_malformed_provider_and_identity_mismatch_fail_closed():
    assert verify(reviewer=lambda _: {"verdicts": []})["reason"] == "MISSING_OR_EXTRA_VERDICTS"
    assert verify(reviewer=lambda _: {"verdicts": [{"evidence_id": "other", "decision": "SUPPORTED", "reason": "yes"}]})["reason"] == "EXPERT_EVIDENCE_ID_MISMATCH"
    assert verify(reviewer=lambda _: {"verdicts": [{"evidence_id": CLAIM["evidence_id"], "decision": "GO", "reason": "yes"}]})["reason"] == "INVALID_EXPERT_VERDICT"
    assert verify(reviewer=lambda _: None)["reason"] == "MALFORMED_EXPERT_RESPONSE"


def test_provider_failure_does_not_leak_exception():
    def fail(_):
        raise RuntimeError("secret bearer token")
    r = verify(reviewer=fail)
    assert r["reason"] == "INDEPENDENT_REVIEW_FAILED"
    assert "secret" not in str(r)
    assert r["go_eligible"] is False


def test_bounded_inputs_and_duplicate_evidence_ids_fail_closed():
    assert verify(claims=[{**CLAIM, "exact_quote": "X" * 801}])["reason"] == "CLAIM_EXCEEDS_BOUNDS"
    two = [CLAIM, {**CLAIM, "interpretation": "другой вывод"}]
    assert verify(claims=two, reviewer=lambda _: {"verdicts": [
        {"evidence_id": CLAIM["evidence_id"], "decision": "SUPPORTED", "reason": "ok"},
        {"evidence_id": "other", "decision": "UNKNOWN", "reason": "нет документа"},
    ]})["reason"] == "EXPERT_EVIDENCE_ID_MISMATCH"
