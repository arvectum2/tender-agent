import pytest

from scripts.research.audit_mos_paper_sessions import audit


def example():
    a={"auctionId":1,"stateId":19000004,"startPrice":100,"auctionCurrentPrice":90}
    b={"id":1,"state":{"id":19000004},"startCost":100,"lastBetCost":90,"contractCost":None,"contracts":[],
       "items":[{"id":1,"currentValue":2,"costPerUnit":50,"skuId":None}],
       "startDate":"13.11.2026 10:00:00","endDate":"13.11.2026 11:00:00",
       "bets":[{"num":1,"id":5,"auctionId":1,"cost":90,"serverTime":"13.11.2026 10:05:00","supplier":{"id":7},"isBlocked":False,"isAutoBet":True}],
       "lastBetId":5,"lastBetSupplier":{"id":7},"uniqueSupplierCount":1}
    return a,b


def test_observation_only():
    a,b=example()
    r=audit(a,b)
    assert r["reduction_percent"]=="10.00" and r["automatic_bids"]==1
    assert r["positions_with_platform_sku_id"]==0 and r["actual_profit_rub"] is None
    assert r["contract_amount_rub"] is None and r["execution_allowed"] is False


@pytest.mark.parametrize("patch",[{"lastBetId":6},{"contractCost":90},{"startCost":200}])
def test_reject_mismatch(patch):
    a,b=example()
    with pytest.raises(ValueError):
        audit(a,b|patch)


def test_identity_disagreement_retained_not_resolved():
    a,b=example()
    r=audit(a,b|{"uniqueSupplierCount":2,"lastBetSupplier":{"id":99}})
    assert not r["participant_count_matches"]
    assert not r["winner_summary_matches_bid_supplier"]
    assert r["execution_allowed"] is False
