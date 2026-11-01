import copy

import pytest

from scripts.market_intelligence import enrich_pq_ntc_vanino_p0_20261101 as m
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    d = {"canonical_id": m.CID, "procedure_id": m.NUMBER,
         "scope": "design", "buyer_inn": None, "platform": None,
         "source_urls": None, "contract_signatory": None}
    return {"id": m.CID, "owner": "tender-agent", "data": d,
            "hash": digest(d), "rev": 1, "meta": {}}


def test_old_null_exact_identity_and_owner():
    good = row()
    m.validate(good)
    for field, value in [("buyer_inn", "wrong"), ("platform", "wrong"),
                         ("source_urls", []), ("scope", "supply")]:
        bad = copy.deepcopy(good)
        bad["data"][field] = value
        bad["hash"] = digest(bad["data"])
        with pytest.raises(RuntimeError):
            m.validate(bad)
    bad = row()
    bad["owner"] = "another"
    with pytest.raises(RuntimeError):
        m.validate(bad)


def test_serializable_cas_and_no_contract_inference():
    old = row()
    d = {**old["data"], "buyer_inn": m.INN, "platform": m.PLATFORM,
         "source_urls": [{"url": m.URL, "tier": "first_party", "sha": m.SHA}]}
    sql = m.sql_for(old, d, {"eis_ntc_vanino_p0": {"source": {"sha256": m.SHA}}},
                    digest(d), {"rows": 118})
    for token in ("ISOLATION LEVEL SERIALIZABLE", "owner FROM dp_collections",
                  "AND (d.data->'platform') IS NULL",
                  "AND (d.data->'buyer_inn') IS NULL",
                  "AND (d.data->'source_urls') IS NULL", "COMMIT;"):
        assert token in sql
    assert d["contract_signatory"] is None


def test_client_source_requires_exact_sha_and_quotes():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_ntc_vanino_sources,
    )

    d = {**row()["data"], "buyer_inn": m.INN, "platform": m.PLATFORM,
         "source_urls": [{"url": m.URL, "tier": "first_party", "sha": m.SHA}]}
    proof = {"eis_ntc_vanino_p0": {
        "fields": ["buyer_inn", "platform", "source_urls"],
        "source": {"url": m.URL, "sha256": m.SHA,
                   "exact_original_quotes": list(m.QUOTES)}}}
    assert len(source_bound_ntc_vanino_sources(d, proof)) == 1
    wrong = copy.deepcopy(proof)
    wrong["eis_ntc_vanino_p0"]["source"]["sha256"] = "0" * 64
    assert source_bound_ntc_vanino_sources(d, wrong) == []
