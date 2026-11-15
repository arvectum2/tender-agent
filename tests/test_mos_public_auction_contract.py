import pytest

from src.modules.tender_connectors.mos_portal.public_auction import (
    detail_row,
    list_row,
    query,
)


def listing():
    return {"auctionId": 123, "tradeType": 1, "id": "Auction123", "number": "123",
            "name": "Товар", "stateId": 19000004, "stateName": "Проведена",
            "customers": [{"name": "Заказчик", "inn": "1234567890"}],
            "winner": {"name": "Поставщик", "inn": "123456789012"},
            "startPrice": 100, "auctionCurrentPrice": 80, "offerCount": 3}


def test_finished_status_and_aggregate_only():
    row = list_row(listing())
    assert row["state"] == "finished"
    result = detail_row({"id": 123, "name": "Товар", "state": {"id": 19000004},
                         "startCost": 100, "lastBetCost": 80, "contractCost": None,
                         "items": [{"id": 2, "skuId": 3, "name": "Товар", "currentValue": 2,
                                    "costPerUnit": 50}]}, row)
    assert result["initial_position_sum_matches"]
    assert result["items"][0]["winning_unit_price_rub"] is None
    assert result["signed_contract_amount"] is None


def test_conflicts_and_no_wrong_state_mapping():
    assert list_row(listing() | {"stateId": 19000005})["state"] == "canceled"
    with pytest.raises(ValueError):
        list_row(listing() | {"id": "Auction124"})
    with pytest.raises(ValueError, match="status"):
        detail_row({"id": 123, "state": {"id": 19000005}}, list_row(listing()))
    assert query()["filter"]["auctionSpecificFilter"]["stateIdIn"] == [19000004, 19000008]
