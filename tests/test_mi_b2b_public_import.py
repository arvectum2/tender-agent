"""Commercial original public card: verify SHA and never infer signed sales."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.market_intelligence.append_b2b_original_card import stage


def _fixture(tmp_path: Path):
    body = (
        '<html><body><h1>Модернизация установки компенсации реактивной мощности (УКРМ)</h1>'
        '4158439 ООО "ЭЛЬБРУС ДРИЛЛИНГ" Дата публикации: 04.09.2025 '
        'Организатор подвел итоги 18.09.2025 и признал процедуру несостоявшейся. '
        'Всего заявок: 0 '
        + "long legitimate public document " * 55 + "</body></html>"
    )
    p = tmp_path / "source.html"
    p.write_text(body, encoding="utf8")
    m = {
        "schema_version": "pq-commercial-primary-source/1",
        "baseline_lots": 106,
        "canonical_id": "commercial:4158439:lot1",
        "primary_url": ("https://www.b2b-center.ru/market/"
                        "modernizatsiia-ustanovki-kompensatsii-reaktivnoi-moshchnosti-ukrm/tender-4158439/"),
        "primary_source_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "private_source_relative": "source.html",
        "buyer": "ООО «ЭЛЬБРУС ДРИЛЛИНГ»",
        "bids_count": 0, "result": "unsuccessful_no_bids", "voltage_kv": None,
        "technical_spec_original_verified": False, "signed_supplier_verified": False,
    }
    dest = tmp_path / "manifest.json"
    dest.write_text(json.dumps(m, ensure_ascii=False), encoding="utf8")
    return p, dest, m


def test_source_bound_card_is_provisional(tmp_path):
    _, path, _ = _fixture(tmp_path)
    row, _ = stage(path, source_root=tmp_path)
    assert row["cid"] == "commercial:4158439:lot1"
    assert row["record"]["technical_voltage_kv"] is None
    assert row["record"]["bids_count"] == 0
    assert row["record"]["supplier_verified"] is False
    assert row["record"]["realized_equipment_revenue_rub"] is None


def test_tampered_source_refused(tmp_path):
    html, manifest, _ = _fixture(tmp_path)
    html.write_bytes(html.read_bytes() + b"CHANGED")
    with pytest.raises(ValueError, match="bytes differ"):
        stage(manifest, source_root=tmp_path)


def test_unsupported_supplier_assertion_refused(tmp_path):
    _, manifest, data = _fixture(tmp_path)
    data["signed_supplier_verified"] = True
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
    with pytest.raises(ValueError, match="unsupported"):
        stage(manifest, source_root=tmp_path)
