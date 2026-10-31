from unittest.mock import patch

import pytest

from scripts.market_intelligence.enrich_pq_filter_signed_32514947144 import (
    CID,
    FIELDS,
    FILES,
    proof,
    write,
)


def test_signed_12kv_capacitor_component_originals():
    p = proof()
    assert CID == "223fz:32514947144:lot1"
    assert len(p["sources"]) == 3
    assert p["sources"][0]["sha256"] == FILES[0][1]
    assert p["role"] == "signed_completed_12kv_capacitor_components_for_500kv_substation"
    assert p["supplier_verified"] is False
    assert p["payment_verified"] is False
    assert FIELDS["pq_equipment_only_contract_rub"] == "3158400.00"
    assert FIELDS["contract_execution_completed"] is True


def test_conflicting_nonempty_field_blocks_before_sql():
    with patch("scripts.market_intelligence.enrich_pq_filter_signed_32514947144.psql") as db:
        with pytest.raises(RuntimeError, match="CAS"):
            write({"id": CID, "owner": "tender-agent",
                   "data": {"contract_registered_price_rub": "1"}},
                  {"rows": 118}, {"sources": [{}, {}, {}]})
        db.assert_not_called()


def test_client_note_requires_source_sha_and_distinguishes_payment():
    from scripts.market_intelligence.enrich_pq_filter_signed_32514947144 import (
        NUM,
    )
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_filter_signed_note,
    )

    data = {
        "canonical_id": CID,
        "contract_registry_number": NUM,
        "contract_registered_price_rub": "3158400.00",
        "pq_equipment_only_contract_rub": "3158400.00",
        "contract_execution_completed": True,
        "registered_signed_contract_verified": True,
    }
    metadata = {
        "eis_contract_enrichment": {
            "role": "signed_completed_12kv_capacitor_components_for_500kv_substation",
            "supplier_verified": False,
            "payment_verified": False,
            "sources": [{"sha256": x[1]} for x in FILES],
        }
    }
    note = source_bound_filter_signed_note(data, metadata)
    assert "3 158 400" in note and "подтверждение оплаты" in note
    assert source_bound_filter_signed_note(data, {}) is None


def test_null_guard_covers_absent_and_json_null_values():
    from pathlib import Path

    source = Path(
        "scripts/market_intelligence/enrich_pq_filter_signed_32514947144.py"
    ).read_text()
    assert "(d.data->>'{k}') IS NULL" in source
    assert "(d.data->'{k}') IS NULL" not in source
