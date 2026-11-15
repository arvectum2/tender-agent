import pytest

from scripts.research.paper_cost_evidence import assess

CUTOFF="2026-11-13T13:00:00+03:00"
POS={"position_id":"1","verified_manufacturer_article":"A-123","unit":"шт","quantity":"100","required_delivery_by":"2026-11-25T12:00:00+03:00"}
OFFER={"position_id":"1","source_kind":"verified_supplier_original","source_url":"https://example.test/item",
       "source_sha256":"a"*64,"observed_at":"2026-11-12T12:00:00+03:00","valid_until":"2026-11-14T12:00:00+03:00",
       "manufacturer_article":"A-123","variant_verified":True,"unit":"шт","available_quantity":"100","minimum_order":"1",
       "unit_price":"351.40","currency":"RUB","price_binding":"firm","vat_basis":"included","delivery_by":"2026-11-20T12:00:00+03:00"}


def test_only_goods_cost_with_no_profit_or_execution():
    r=assess(POS,OFFER,CUTOFF)
    assert r["eligible_for_paper_cost"] and r["observed_goods_cost_rub"]=="35140.00"
    assert r["profit_rub"] is None and r["execution_allowed"] is False


@pytest.mark.parametrize("patch,reason",[
    ({"observed_at":"2026-11-15T12:00:00+03:00"},"NOT_AVAILABLE_AT_DECISION_TIME"),
    ({"valid_until":None},"TIME_OR_VALIDITY_UNKNOWN"),
    ({"source_kind":"search_snippet"},"SOURCE_NOT_VERIFIED_ORIGINAL"),
    ({"manufacturer_article":"A-124"},"EXACT_ITEM_OR_UNIT_UNVERIFIED"),
    ({"variant_verified":False},"EXACT_ITEM_OR_UNIT_UNVERIFIED"),
    ({"available_quantity":"2"},"STOCK_OR_MINIMUM_ORDER_UNVERIFIED"),
    ({"unit_price":"1","price_binding":"placeholder"},"BINDING_PRICE_UNKNOWN"),
    ({"vat_basis":"unknown"},"VAT_UNKNOWN"),
    ({"delivery_by":None},"DELIVERY_UNVERIFIED"),
])
def test_fail_closed(patch,reason):
    r=assess(POS,OFFER|patch,CUTOFF)
    assert not r["eligible_for_paper_cost"] and reason in r["reasons"]
    assert r["observed_goods_cost_rub"] is None
