import pytest

from scripts.market_intelligence.enrich_pq_reto_20261031 import FIELDS, validate_texts


def test_commission_winner_not_signed_supplier():
    assert FIELDS['commission_winner_name']=='ООО «ЭКСПЕРТ ГРУПП»'
    assert FIELDS['pq_equipment_only_contract_rub']=='3050000.00'
    assert not any('supplier' in key for key in FIELDS)

def test_false_original_rejected():
    with pytest.raises(ValueError):validate_texts('EIS 3050000','RAD winner')
