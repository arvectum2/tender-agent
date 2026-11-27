from unittest.mock import patch

import pytest

from scripts.market_intelligence.enrich_pq_eis_contract_32514476448 import (
    CID,
    FIELDS,
    FILES,
    proof,
    write,
)


def test_original_eis_contract_is_epc_not_device_sale():
    p = proof()
    assert CID == "223fz:32514476448:lot1"
    assert len(p["sources"]) == 3
    assert p["sources"][0]["sha256"] == FILES[0][1]
    assert p["role"] == "registered_completed_epc_not_equipment_sale"
    assert p["supplier_verified"] is False
    assert p["payment_verified"] is False
    assert FIELDS["registered_signed_contract_verified"] is True


def test_existing_field_blocks_before_sql():
    with patch(
        "scripts.market_intelligence.enrich_pq_eis_contract_32514476448.psql"
    ) as db:
        with pytest.raises(RuntimeError, match="CAS"):
            write(
                {
                    "id": CID,
                    "owner": "tender-agent",
                    "data": {"contract_registered_price_rub": "1"},
                },
                {"rows": 117},
                {"sources": [{}, {}, {}]},
            )
        db.assert_not_called()
