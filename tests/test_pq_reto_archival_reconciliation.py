"""Regression: archive winner ≠ signed supplier or equipment-only 6–35kV sale."""
import json
from pathlib import Path


def test_reto_original_protocol_recheck_keeps_gates_separate():
    p = (Path(__file__).resolve().parents[1] / "docs/market_intelligence"
         / "PQ_RETO_12KV_RECONCILIATION_20261029.json")
    obj = json.loads(p.read_text(encoding="utf-8"))
    award = obj["original_award_protocol"]
    contract = obj["historical_contract_registry"]
    assert obj["canonical_id"] == "223fz:32616181358:lot1"
    assert obj["new_notice_added_to_live_corpus"] is False
    assert award["exact_byte_match_prior_archive"] is True
    assert len(award["sha256"]) == 64
    assert award["winner_name"] == "ООО «ЭКСПЕРТ ГРУПП»"
    assert award["winning_offer_including_vat_rub"] == "3050000.00"
    assert contract["historical_price_rub"] == "3050000.00"
    assert contract["independent_current_card_http"] == 404
    assert contract["current_original_byte_match"] is False
    assert contract["signed_supplier_identity_publicly_verified"] is False
    assert award["contract_signer_verification"] is False
    assert award["oem_verification"] is False
    assert obj["signed_supplier_count_added"] == 0
    assert obj["verified_core_6_35kv_sales_rub_added"] == 0
