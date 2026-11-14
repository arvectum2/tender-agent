"""Fail-closed unit tests for source-bound Meleuz enrichment."""
import pytest

from scripts.market_intelligence.enrich_pq_meleuz_20261031 import (
 CID,
 FIELDS,
 norm,
 validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
 data={'canonical_id':CID,'procedure_id':'32616296475','supplier_verified':False,
       'pq_equipment_only_contract_rub':None,'evidence':[]}
 return {'id':CID,'owner':'tender-agent','data':data,'hash':digest(data),
         'rev':1,'meta':{}}

def test_source_fields_are_requirements_not_equipment_sales():
 assert 'не более' in FIELDS['voltage_kv']
 assert 'не менее' in FIELDS['power']
 assert 'equipment_only_price' not in FIELDS
 assert 'supplier_inn' not in FIELDS

def test_old_null_case_allowed():
 validate(row())

def test_reject_existing_field():
 r=row();r['data']['contract_number']='existing';r['hash']=digest(r['data'])
 with pytest.raises(RuntimeError,match='CAS'):validate(r)

def test_reject_identity_and_content_hash_drift():
 r=row();r['id']='other'
 with pytest.raises(RuntimeError):validate(r)
 r=row();r['data']['supplier_verified']=True
 with pytest.raises(RuntimeError):validate(r)

def test_normalization():
 assert norm('  6,3\xa0 кВ  ')=='6,3 кВ'

