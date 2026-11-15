from decimal import Decimal

import pytest

from src.modules.paper_trading.auction_economics import (
    cost_ceiling,
    scenario_report,
    verified_bid_trace,
)


def test_inverse_cost_ceiling_and_no_fake_profit():
    r=cost_ceiling("132.16", logistics=".08", overhead=".07", contingency=".03", markup=".12")
    assert r["max_supplier_basket_rub"] == "100.00"
    assert r["actual_profit_rub"] is None
    assert r["trade_decision"] == "INSUFFICIENT_COST_EVIDENCE"
    r=cost_ceiling("100", logistics=0, overhead=0, contingency=0, markup=0, fixed=110)
    assert r["max_supplier_basket_rub"] is None
    with pytest.raises(ValueError):
        cost_ceiling("100", logistics=0, overhead=0, contingency=0, markup=0, variable_revenue_fee=1)


def source():
    l={"auctionId":123,"tradeType":1,"id":"Auction123","number":"123","name":"Товар",
       "stateId":19000004,"stateName":"Проведена","customers":[{"name":"Заказчик"}],
       "winner":{"name":"Лидер","inn":"1234567890","supplierId":7},
       "startPrice":100,"auctionCurrentPrice":80,"offerCount":2}
    d={"id":123,"name":"Товар","state":{"id":19000004},"startCost":100,"lastBetCost":80,
       "startDate":"13.11.2026 10:00:00","endDate":"13.11.2026 12:00:00",
       "lastBetId":2,"lastBetSupplier":{"id":7,"name":"Лидер"},"uniqueSupplierCount":2,
       "items":[{"id":3,"skuId":5,"name":"Товар","currentValue":2,"costPerUnit":50}],
       "bets":[{"num":2,"id":2,"auctionId":123,"cost":80,"serverTime":"13.11.2026 11:00:00",
                "isAutoBet":True,"isBlocked":False},
               {"num":1,"id":1,"auctionId":123,"cost":90,"serverTime":"13.11.2026 10:30:00",
                "isAutoBet":False,"isBlocked":False}]}
    return l,d


def test_verified_sequence_and_scope():
    l,d=source()
    result=verified_bid_trace(l,d)
    assert result["reduction_percent"]=="20.00"
    assert result["automatic_bids"]==1
    assert result["signed_contract_amount_rub"] is None
    assert result["positions"][0]["winning_unit_price_rub"] is None
    s=scenario_report(result)
    assert s["benchmark_is_ex_post"] and not s["claims_counterfactual_win"]
    assert Decimal(s["scenarios"][0]["max_supplier_basket_rub"]) > Decimal(s["scenarios"][-1]["max_supplier_basket_rub"])


def test_reject_missing_and_invalid_bids():
    l,d=source()
    with pytest.raises(ValueError,match="incomplete"):
        verified_bid_trace(l,d|{"bets":d["bets"][:1]})
    with pytest.raises(ValueError,match="winner"):
        verified_bid_trace(l,d|{"lastBetSupplier":{"id":99,"name":"Other"}})
    d["bets"][0]["isBlocked"]=True
    with pytest.raises(ValueError,match="inconsistent"):
        verified_bid_trace(l,d)
