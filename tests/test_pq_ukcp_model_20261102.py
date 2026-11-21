"""UKCP model reference is not awarded supplier and never overwrites values."""
import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_ukcp_model_20261102 import (
    CID,
    FIELDS,
    SOURCES,
    prepared,
    proof,
    validate,
)


def test_exact_first_party_sha_and_guarded_nulls():
    sources=proof()
    assert len(sources)==2
    assert [x['sha256'] for x in sources]==[s[1] for s in SOURCES]
    d={'canonical_id':CID,'procedure_id':'4643332','scope':'supply','quantity':1,
       'customer':{'inn':'2709015787'},'description':'КЭП3-10,5-150-3У2',
       'evidence':[{'url':SOURCES[0][2]}]}
    row={'id':CID,'owner':'tender-agent','rev':1,'hash':digest(d),'data':d,'meta':{}}
    validate(row)
    data,meta,h=prepared(row,sources)
    assert h==digest(data) and data['equipment_voltage_kv']=='10.5'
    assert meta['ukcp_model_reference_20261102']['awarded_oem_verified'] is False
    for field in FIELDS:
        bad={**d,field:'conflict'}
        with pytest.raises(RuntimeError):
            validate({**row,'data':bad,'hash':digest(bad)})
