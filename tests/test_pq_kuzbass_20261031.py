"""No buyer/supplier/contract inference from a commission protocol."""
import pytest

from scripts.market_intelligence import enrich_pq_kuzbass_20261031 as m
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data={'canonical_id':m.CID,'procedure_id':'32514947144','scope':'supply_components',
          'nmck_rub':'3186960','supplier_verified':False,'evidence':[],
          'market_scope':'filter_capacitor_components_nominal_voltage_unverified'}
    return {'id':m.CID,'owner':'tender-agent','hash':digest(data),'rev':2,
            'data':data,'meta':{}}


def test_source_bound_fields_preserve_non_sale_status():
    r=row();m.validate(r)
    sources=[{'url':'https://zakupki.gov.ru/x','sha256':'a'*64}]
    d,meta,h=m.build(r,sources)
    assert h==digest(d)
    assert d['commission_winner_name']==m.WINNER
    assert d['commission_bid_rub']=='3158400.00'
    assert d['technical']['application_substation_voltage_kv']=='500'
    assert d.get('registered_signed_contract_verified') is None
    assert d.get('supplier_verified') is False
    assert d.get('paid_amount_rub') is None
    assert meta['kuzbass_20261031_p2_p3']['commission_winner_not_signed_supplier']


def test_conflicting_nonnull_or_identity_fail_closed():
    for field,value in [('commission_winner_name','conflict'),('quantity',13),('power','other')]:
        r=row();r['data'][field]=value;r['hash']=digest(r['data'])
        with pytest.raises(RuntimeError):m.validate(r)
    r=row();r['owner']='other'
    with pytest.raises(RuntimeError):m.validate(r)
    r=row();r['hash']='0'*64
    with pytest.raises(RuntimeError):m.validate(r)
