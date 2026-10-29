"""Incremental DB source gate must fail closed without connecting to PostgreSQL."""
import hashlib
import json

import pytest

from scripts.market_intelligence import append_pq_delta_20261029 as mod


def _fake_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    originals = []
    for i in range(3):
        raw = f"original public evidence document {i}".encode()
        filename = f"document-{i}.pdf"
        (tmp_path / filename).write_bytes(raw)
        originals.append({
            "private_relative": filename, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw)
        })
    case = {
        "canonical_id": "223fz:32413764701:lot1",
        "procedure_id": "32413764701",
        "signed_supplier_verified": False,
        "supplier_verified": False,
        "paid_verified": False,
        "realized_equipment_revenue_rub": None,
        "family": "ukrm", "scope": "equipment_supply_new", "market_scope": "core_10kv",
        "customer": {"name": "buyer"}, "status": "staged_unreviewed",
        "nmck_rub": "123.00",
        "evidence": [{"url": "https://zakupki.gov.ru/source",
                      "sha256": originals[0]["sha256"], "source_tier": "primary"}],
    }
    data = {
        "schema_version": "mi-pq-source-bound-incremental/1",
        "new_cases": [{"source_record": case, "verified_originals": originals}],
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data), encoding="utf8")
    return p, data


def test_offline_stage_is_sha_bound(tmp_path, monkeypatch):
    p, _ = _fake_manifest(tmp_path, monkeypatch)
    rows, _ = mod.source_data(p)
    assert len(rows) == 1
    assert len(rows[0]["hash"]) == 64
    assert rows[0]["record_metadata"]["source_content_hash"] == rows[0]["hash"]
    assert rows[0]["metadata"]["winning_supplier_only_if_verified"] is None


def test_refuse_tampered_original(tmp_path, monkeypatch):
    p, _ = _fake_manifest(tmp_path, monkeypatch)
    (tmp_path / "document-0.pdf").write_bytes(b"altered")
    with pytest.raises(ValueError, match="SHA or size drift"):
        mod.source_data(p)


def test_refuse_supplier_inference(tmp_path, monkeypatch):
    p, data = _fake_manifest(tmp_path, monkeypatch)
    data["new_cases"][0]["source_record"]["supplier_verified"] = True
    p.write_text(json.dumps(data), encoding="utf8")
    with pytest.raises(ValueError, match="unverified supplier"):
        mod.source_data(p)


def test_refuse_duplicate_notice_lot(tmp_path, monkeypatch):
    p, data = _fake_manifest(tmp_path, monkeypatch)
    data["new_cases"].append(data["new_cases"][0])
    p.write_text(json.dumps(data), encoding="utf8")
    with pytest.raises(ValueError, match="Bad/duplicate identity"):
        mod.source_data(p)
