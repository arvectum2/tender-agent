"""The TEK-Torg buyer identity may enrich a null field, not a signed sale."""
import json
from unittest.mock import patch

import pytest

from scripts.market_intelligence import enrich_pq_rn61005187_buyer_inn as target
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row(inn=None):
    data = {
        "canonical_id": target.CID,
        "procedure_id": "РН61005187",
        "scope": "supply",
        "customer": {"name": "ООО «Харампурнефтегаз»", "inn": inn},
        "description": "Поставка ДФКУ, УКРМ",
        "publication_date": "2026-10-23",
        "evidence": [{"source_tier": "third_party"}],
    }
    return {"id": target.CID, "owner": "tender-agent", "hash": digest(data),
            "rev": 2, "data": data, "meta": {}}


def test_first_party_identity_dry_run_only(capsys):
    with (patch.object(target, "proof", return_value={"url": target.URL,
            "sha256": target.SHA}),
          patch.object(target, "get_row", return_value=row()),
          patch.object(target, "snapshot", return_value={"rows": 123}),
          patch("sys.argv", ["enrich_pq_rn61005187_buyer_inn"])):
        target.main()
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "dry_run"
    assert result["field"] == "customer.inn"
    assert result["value"] == "7536125117"
    assert result["before"]["rows"] == 123


def test_nonnull_inn_blocks_update():
    with (patch.object(target, "proof", return_value={"url": target.URL,
            "sha256": target.SHA}),
          patch.object(target, "get_row", return_value=row("1111111111")),
          patch("sys.argv", ["enrich_pq_rn61005187_buyer_inn"]),
          pytest.raises(RuntimeError, match="CAS")):
        target.main()


def test_receipt_alias_is_not_canonical_id():
    assert target.RAW_CASE_ID == "commercial:RN61005187:lot1"
    assert target.CID == "commercial:РН61005187:lot1"
    assert target.RAW_CASE_ID != target.CID
