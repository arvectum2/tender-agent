import copy

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import ri223_owner_review as review
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)


def scenario(price='900000'):
    return ExplicitCostScenarioRequest(external_direct_rub='250000',labor_rub='300000',
        reserve_rub='50000',fixed_platform_fees_rub='10000',revenue_tax_percent='6',
        variable_platform_fee_percent='1',target_profit_rub='100000',
        offer_scenario={'offer_price_rub':price,'nonrefundable_guarantee_fees_rub':'5000',
                        'refundable_bid_cash_rub':'20000','refundable_contract_cash_rub':'100000'},
        accept_hypothetical_assumptions_only=True)


def notice():
    return {'status':'PINNED_RI223_ARCHIVED_NOTICE','lot_count':1,
            'fields':{'single_lot_currency':'RUB','single_lot_initial_sum':'1020000'},
            'citations':[{'source_sha256':'a'*64}]}


def test_historical_not_current():
    data=review.historical_owner_reference()
    assert data['historical_completed_count']==0 and data['as_of_date']=='2026-10-13'
    assert data['current_reference_count'] is None and not data['current_profile_bound']


def test_changed_owner_receipt(tmp_path,monkeypatch):
    path=tmp_path/'source.json'
    path.write_bytes(b'{}')
    monkeypatch.setattr(review,'_OWNER_RECEIPT',path)
    assert review.historical_owner_reference()['status']=='UNKNOWN'


@pytest.mark.parametrize('change',['multi','currency','source','missing','zero'])
def test_no_unverified_lot(change):
    n=notice()
    if change=='multi':n['lot_count']=2
    elif change=='currency':n['fields']['single_lot_currency']='USD'
    elif change=='source':n['status']='UNKNOWN'
    elif change=='missing':n['fields'].pop('single_lot_initial_sum')
    elif change=='zero':n['fields']['single_lot_initial_sum']='0'
    assert review.lot_scenario(n,scenario())['status']=='UNKNOWN'


def test_explicit_only():
    assert review.lot_scenario(notice(),None)['status']=='UNKNOWN'
    s=scenario();s.accept_hypothetical_assumptions_only=False
    with pytest.raises(HTTPException):review.lot_scenario(notice(),s)


@pytest.mark.parametrize('price,within',[('900000',True),('1100000',False)])
def test_price_comparison(price,within):
    out=review.lot_scenario(notice(),scenario(price))
    assert out['offer_within_archived_initial_sum']==within
    assert out['target_threshold_within_archived_initial_sum']
    assert not out['commercial_owner_go'] and not out['actual_costs_verified']


def test_missing_inventory_prevents_review(monkeypatch,tmp_path):
    meta={}
    monkeypatch.setattr(review,'checked_search_run',lambda _:(tmp_path,meta))
    monkeypatch.setattr(review,'ri223_archive_observation',lambda *a:notice())
    monkeypatch.setattr(review,'verified_inventory',lambda *a:{'archived_bytes_complete':True,'projection_complete':False})
    monkeypatch.setattr(review,'sme_observation',lambda *a:pytest.fail('incomplete source read'))
    assert review.review_archived_owner_run('fixture',scenario())['status']=='UNKNOWN'


def test_changed_source_clears_result(monkeypatch,tmp_path):
    meta={'files':[]};changed=copy.deepcopy(meta);changed['tamper']=True
    reads=iter([(tmp_path,meta),(tmp_path,changed)])
    monkeypatch.setattr(review,'checked_search_run',lambda _:next(reads))
    monkeypatch.setattr(review,'ri223_archive_observation',lambda *a:notice())
    monkeypatch.setattr(review,'verified_inventory',lambda *a:{'archived_bytes_complete':True,'projection_complete':True})
    monkeypatch.setattr(review,'sme_observation',lambda *a:{'status':'UNKNOWN'})
    monkeypatch.setattr(review,'scoring_observation',lambda *a:{'status':'UNKNOWN'})
    result=review.review_archived_owner_run('fixture',scenario())
    assert result['status']=='UNKNOWN' and 'economics' not in result
