"""Safety guards for sole-participant source-bound enrichment."""
import copy

import pytest

from scripts.market_intelligence.enrich_pq_bashkirenergo_commission_20261102 import (
    CID,
    FIELDS,
    KEY,
    prepare,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {
        "canonical_id": CID,
        "procedure_id": "32515582393",
        "scope": "supply",
        "customer": {"inn": "0277071467"},
        "contract_registered_price_rub": "4850000.00",
        "registered_signed_contract_verified": True,
        "winner": None,
        "contract_signatory": None,
        "evidence": [],
    }
    return {"id": CID, "owner": "tender-agent", "data": data,
            "hash": digest(data), "rev": 3, "meta": {}}


def test_selected_sole_participant_is_not_signed_supplier_or_winner():
    data, meta, h = prepare(row(), {"zip_sha256": "verified"})
    assert data["commission_selected_participant"] == "ООО «УК КОНДЕНСАТОР»"
    assert data["bid"] == "4900000.00"
    assert data["negotiated_offer_rub"] == "4850000.00"
    assert data["winner"] is None and data["contract_signatory"] is None
    assert meta[KEY]["signed_supplier_verified"] is False
    assert meta[KEY]["paid_pq_equipment_sale_verified"] is False
    assert h == digest(data)


@pytest.mark.parametrize("change", [
    lambda r: r["data"].update({"bid": "1"}),
    lambda r: r["data"].update({"winner": "someone"}),
    lambda r: r["data"].update({"contract_registered_price_rub": "0"}),
    lambda r: r["data"]["customer"].update({"inn": "0000000000"}),
    lambda r: r["meta"].update({KEY: {}}),
    lambda r: r.update({"owner": "other"}),
    lambda r: r.update({"hash": "0" * 64}),
])
def test_rejects_conflict_and_identity_drift(change):
    r = copy.deepcopy(row())
    change(r)
    with pytest.raises(RuntimeError, match="guard"):
        prepare(r, {"zip_sha256": "verified"})


def test_no_existing_field_is_overwritten():
    assert set(FIELDS) == {
        "bid", "commission_selected_participant",
        "negotiated_offer_rub", "protocol_status_note",
    }
