"""Regression: two registered contracts must not become PQ sales or a single award."""
import pytest

from scripts.market_intelligence.enrich_pq_evraz_two_contracts_20261101 import (
    CID,
    FIELDS,
    NUMBERS,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def test_dual_contracts_preserve_separate_identities_and_no_supplier():
    entries = FIELDS['contract_registry_entries']
    assert [e['registry_number'] for e in entries] == list(NUMBERS)
    assert [e['registered_price_rub'] for e in entries] == ['1043734.03', '13090401.45']
    assert 'Заявок нет' not in FIELDS['contract_status_note']  # exact source quote remains in proof
    assert 'заявок нет' in FIELDS['contract_status_note'].lower()
    assert 'supplier_inn' not in FIELDS and 'paid_amount_rub' not in FIELDS
    assert 'pq_equipment_only_contract_rub' not in FIELDS
    assert 'contract_registry_number' not in FIELDS


def test_identity_and_old_null_guard():
    data = {'canonical_id': CID, 'procedure_id': '32413195287',
            'scope': 'mixed_epc_repair_services', 'nmck_rub': '13892027.33'}
    row = {'id': CID, 'owner': 'tender-agent', 'data': data,
           'hash': digest(data), 'meta': {}}
    validate(row)
    row['data'] = {**data, 'registered_signed_contract_verified': True}
    row['hash'] = digest(row['data'])
    with pytest.raises(RuntimeError, match='conflict'):
        validate(row)
