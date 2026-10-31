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
