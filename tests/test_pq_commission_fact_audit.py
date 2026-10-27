import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_commission_fact_audit import verify


def _set_up(tmp_path: Path):
    queue = tmp_path / "queue"
    queue.mkdir()
    ident = "32514947144-" + "a" * 24
    text = "Признать заявку ООО «ФИЛЬТР» победителем; цена 3 158 400,00, НМЦ 3 186 960,00"
    (queue / (ident + ".json")).write_text(json.dumps({
        "schema_version": "pq-review-queue/1", "state": "reviewed",
        "packet": {"registry_number": "32514947144",
                   "documents": [{"sha256": "b" * 64, "text": text,
                                  "method": "docx"}]}}))
    facts = tmp_path / "facts.json"
    fact = {
        "procedure_id": "32514947144", "queue_id": ident,
        "source_sha256": "b" * 64,
        "source_quote": "Признать заявку ООО «ФИЛЬТР» победителем",
        "amount_quote": "3 158 400,00", "nmck_quote": "3 186 960,00",
        "proposed_or_selected_participant": "ООО «ФИЛЬТР»",
        "offer_rub": "3158400.00", "nmck_rub": "3186960.00",
        "market_category": "filter_capacitor_supply",
        "decision_type": "commission_winner_selected",
        "price_kind": "commission_offer_vat",
        "signed_contract_verified": False, "supplier_of_signed_contract_verified": False,
    }
    facts.write_text(json.dumps({"schema_version": "pq-commission-facts/1",
                                 "facts": [fact]}))
    return facts, queue


def test_valid_original_quote_is_not_signed_contract(tmp_path: Path):
    facts, queue = _set_up(tmp_path)
    result = verify(facts=facts, queue=queue)
    assert result["facts_accepted"] == 1
    assert result["verified_signed_contracts"] == 0
    record = result["records"][0]
    assert record["commission_decision_source_verified"] is True
    assert record["bid_minus_nmck_rub"] == "-28560.00"
    assert record["supplier_of_signed_contract_verified"] is False


def test_quote_or_sha_mismatch_refused(tmp_path: Path):
    facts, queue = _set_up(tmp_path)
    data = json.loads(facts.read_text())
    data["facts"][0]["amount_quote"] = "999,99"
    facts.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Quoted proposed offer"):
        verify(facts=facts, queue=queue)
    data["facts"][0]["amount_quote"] = "3 158 400,00"
    data["facts"][0]["source_sha256"] = "0" * 64
    facts.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Source document SHA"):
        verify(facts=facts, queue=queue)


def test_signed_claim_refused_without_actual_contract(tmp_path: Path):
    facts, queue = _set_up(tmp_path)
    data = json.loads(facts.read_text())
    data["facts"][0]["signed_contract_verified"] = True
    facts.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="cannot certify"):
        verify(facts=facts, queue=queue)
