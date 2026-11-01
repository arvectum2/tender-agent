"""Guardrails for source-bound buyer identity enrichment."""
import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_roseltorg_buyer_inns_20261101 import (
    CASES,
    validate,
)


@pytest.mark.parametrize('case', CASES)
def test_old_null_only_and_nested_customer_match(case):
    n, inn, scope, *_ = case
    cid = f'223fz:{n}:lot1'
    data = {'canonical_id':cid,'procedure_id':n,'scope':scope,
            'customer':{'inn':inn},'buyer_inn':None}
    row = {'id':cid,'owner':'tender-agent','data':data,'hash':digest(data),'meta':{}}
    validate(case,row)
    for changed in ({'buyer_inn':'1234567890'},{'customer':{'inn':'0000000000'}}):
        bad = {**data,**changed}
        with pytest.raises(RuntimeError):
            validate(case,{**row,'data':bad,'hash':digest(bad)})
    with pytest.raises(RuntimeError):
        validate(case,{**row,'owner':'someone-else'})
