from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.market_intelligence.enrich_pq_filter_signed_32515029641 import (
    CID,
    FIELDS,
    NUM,
    SOURCES,
    evidence,
    validate,
)


def test_primary_signed_registry_and_named_commission_bidder():
    p = evidence()
    assert CID == "223fz:32515029641:lot1"
    assert NUM == "54716016979250033980000"
    assert len(p["sources"]) == 5
    assert [x["sha256"] for x in p["sources"]] == [x[1] for x in SOURCES]
    assert p["signed_supplier_identity"] == "unverified"
    assert p["paid_amount"] == "unverified"
    assert FIELDS["registered_signed_contract_verified"] is True
    assert FIELDS["contract_registered_price_rub"] == "3490560.00"
    assert FIELDS["quantity"] * int(FIELDS["unit_price_rub"].split(".")[0]) == 3490560


def test_conflicting_existing_field_blocks():
    with patch("scripts.market_intelligence.enrich_pq_filter_signed_32515029641.psql") as db:
        with pytest.raises((RuntimeError, KeyError)):
            validate({
                "id": CID, "owner": "tender-agent", "hash": "0" * 64,
                "data": {
                    "canonical_id": CID, "procedure_id": "32515029641",
                    "scope": "supply_components", "nmck_rub": "3621456",
                    "commission_bid_rub": "1",
                },
                "meta": {},
            })
        db.assert_not_called()


def test_sql_null_guard_covers_json_absent_or_null():
    source = Path(
        "scripts/market_intelligence/enrich_pq_filter_signed_32515029641.py"
    ).read_text()
    assert "(d.data->>'{k}') IS NULL" in source
    assert "BEGIN ISOLATION LEVEL SERIALIZABLE" in source
    assert "verify_internal_runtime" in source
    assert "verified_backup" in source


def test_customer_report_note_requires_exact_source_shas():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_filter_south_signed_note,
        verified_filter_south_signed_contract,
    )

    d = {
        "canonical_id": CID,
        "scope": "supply_components",
        "contract_registry_number": NUM,
        "contract_registered_price_rub": "3490560.00",
        "pq_equipment_only_contract_rub": "3490560.00",
        "quantity": 12,
        "unit_price_rub": "290880.00",
        "registered_signed_contract_verified": True,
        "contract_execution_status_verified": "Исполнение",
    }
    m = {"eis_filter_32515029641_enrichment": {
        "sources": [{"sha256": x[1]} for x in SOURCES],
        "signed_supplier_identity": "unverified",
        "paid_amount": "unverified",
    }}
    assert verified_filter_south_signed_contract(d, m)
    note = source_bound_filter_south_signed_note(d, m)
    assert "3 490 560" in note
    assert "не подтверждение завершения или оплаты" in note
    assert source_bound_filter_south_signed_note(d, {}) is None
