"""Focused source and old-null CAS checks."""
import pytest

from scripts.market_intelligence.enrich_pq_bidzaar_sibsteklo_inn_20261102 import (
    CID,
    INN,
    KEY,
    LEGAL_NAME,
    PROFILE_QUOTE,
    TECH_SHA,
    TECH_URL,
    check_identity,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def test_exact_two_source_identity():
    check_identity((LEGAL_NAME + " " + PROFILE_QUOTE).encode(), b"PK\x03\x04docx")
    with pytest.raises(ValueError):
        check_identity((LEGAL_NAME + " ИНН/КПП: 0000000000/000000000").encode(),
                       b"PK\x03\x04docx")


def test_missing_fields_and_source_required():
    d = {"canonical_id": CID, "procedure_id": "306-644", "scope": "epc",
         "customer": {"name": "СИБСТЕКЛО", "inn": None},
         "evidence": [{"url": TECH_URL, "sha256": TECH_SHA}]}
    row = {"id": CID, "owner": "tender-agent", "data": d,
           "hash": digest(d), "rev": 1, "meta": {}}
    validate(row)
    for changed in (
        {**d, "buyer_inn": INN},
        {**d, "customer": {**d["customer"], "inn": INN}},
        {**d, "evidence": []},
    ):
        with pytest.raises(RuntimeError):
            validate({**row, "data": changed, "hash": digest(changed)})
    with pytest.raises(RuntimeError):
        validate({**row, "meta": {KEY: True}})
