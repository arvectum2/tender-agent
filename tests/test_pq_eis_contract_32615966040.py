from unittest.mock import patch

import pytest

from scripts.market_intelligence.enrich_pq_eis_contract_32615966040 import (
 CID,
 FIELDS,
 FILES,
 proof,
 write,
)


def test_original_contract_two_sha_bound_cards():
 p=proof()
 assert len(p['sources'])==2 and p['sources'][0]['sha256']==FILES[0][1]
 assert p['supplier_verified'] is False and p['payment_verified'] is False
 assert FIELDS['contract_registered_price_rub']=='5273763.77'

def test_conflicting_nonempty_field_blocks_without_sql():
 with patch('scripts.market_intelligence.enrich_pq_eis_contract_32615966040.psql') as db:
  with pytest.raises(RuntimeError,match='CAS'):
   write({'id':CID,'owner':'tender-agent','data':{'contract_registered_price_rub':'1'}},{'rows':118},{'sources':[{},{}]})
  db.assert_not_called()
