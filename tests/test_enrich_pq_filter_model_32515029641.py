import pytest

from scripts.market_intelligence.enrich_pq_filter_model_32515029641 import (
    CID,
    FIELDS,
    MODEL,
    SOURCES,
    model_rating_from_text,
    prepared,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def sample():
    data = {"canonical_id": CID, "procedure_id": "32515029641",
            "scope": "supply_components", "quantity": 12, "equipment_model": MODEL,
            "evidence": [{"url": SOURCES[1][3], "sha256": SOURCES[1][2]}]}
    return {"id": CID, "owner": "tender-agent", "hash": digest(data),
            "rev": 4, "meta": {}, "data": data}


def test_exact_model_rating():
    text = "Конденсатор КЭПФ-12-450-2 УХЛ1 (или эквивалент) Напряжение, кВ - 12 ; Емкость, мкФ – 9,95; Мощность, квар – 450 ;"
    assert model_rating_from_text(text)
    assert not model_rating_from_text(text.replace("кВ - 12", "кВ - 6"))
    assert not model_rating_from_text(text.replace("квар – 450", "квар – 300"))


def test_guarded_null_fields():
    row = sample()
    validate(row)
    data, meta, sha = prepared(row, [{"url": "official", "sha256": "a" * 64}])
    assert {k: data[k] for k in FIELDS} == FIELDS
    assert data["quantity"] == 12 and sha == digest(data)
    assert "paid sale" in meta["eis_filter_model_crosscase_20261102"]["not"]


@pytest.mark.parametrize("field,value", [
    ("equipment_voltage_kv", "6"), ("power", "0"), ("scope", "mixed_epc"),
    ("equipment_model", "КЭПФ-10-450-2 УХЛ1"), ("evidence", []),
])
def test_conflicting_field_fails(field, value):
    row = sample()
    row["data"][field] = value
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError):
        validate(row)


def test_hash_drift_fails():
    row = sample()
    row["hash"] = "0" * 64
    with pytest.raises(RuntimeError):
        validate(row)
