"""Regression checks for source-bound, null-only Nagornaya contract enrichment."""
import copy

import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_nagornaya_contract_20261103 import (
    CID,
    FIELDS,
    Text,
    validate,
)


def row():
    data = {"canonical_id": CID, "procedure_id": "32615614821", "scope": "epc",
            "nmck_rub": "1432983.66", "reported_contract_total_rub": "1833358.30",
            "contract_date": "2026-04-14", "supplier_verified": False,
            "pq_equipment_only_contract_rub": None}
    return {"id": CID, "owner": "tender-agent", "hash": digest(data),
            "data": data, "meta": {}, "rev": 2}


def test_accepts_exact_identity_and_null_fields():
    validate(row(), {"sources": [{"sha256": "a"}, {"sha256": "b"}]})


@pytest.mark.parametrize("change", ["owner", "scope", "non_null", "hash", "supplier"])
def test_fails_closed_on_conflict(change):
    value = copy.deepcopy(row())
    if change == "owner":
        value["owner"] = "other"
    elif change == "scope":
        value["data"]["scope"] = "supply"
    elif change == "non_null":
        value["data"]["contract_registry_number"] = "old"
    elif change == "hash":
        value["hash"] = "0" * 64
    else:
        value["data"]["supplier_verified"] = True
    with pytest.raises(RuntimeError, match="CAS"):
        validate(value, {"sources": [{"sha256": "a"}, {"sha256": "b"}]})


def test_only_registered_contract_not_supplier_or_payment():
    assert len(FIELDS) == 6
    assert FIELDS["contract_registered_price_rub"] == FIELDS["protocol_offer_rub"]
    assert "supplier_verified" not in FIELDS
    assert "paid_verified" not in FIELDS


def test_html_text_parser_ignores_scripts():
    parser = Text()
    parser.feed("<p>Протокол</p><script>secret</script><div>1 833 358.30</div>")
    assert "Протокол" in parser.parts
    assert "secret" not in parser.parts
