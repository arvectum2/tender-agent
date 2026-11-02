"""Verify source provenance and conservative classification offline."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.market_intelligence import append_pq_uralkali_4263966 as mod


def test_source_sha_receipt_quotes_fail_closed(tmp_path, monkeypatch):
    quotes = ("№ 4263966", "N=200кВАр_Uн=10кВ", "Всего 1 позиция")
    name = "test.bin"
    rel = "captures/commercial_4263966_lot1/" + name
    url = mod.URL + "positions/"
    raw = ("<html><body>" + " ".join(quotes) + "</body></html>").encode()
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    f.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    receipt = {"sha256": sha, "bytes": len(raw), "source_url": url,
               "case_id": mod.CID, "http_status": 200, "relative_file": rel}
    Path(str(f) + ".json").write_text(json.dumps(receipt))
    monkeypatch.setattr(mod, "ORIGINALS", ((name, sha, url, quotes),))
    row = mod.stage(tmp_path)
    assert row["record"]["equipment_voltage_kv"] == "10"
    assert row["record"]["reactive_power_kvar"] == 200
    assert row["record"]["signed_supplier_verified"] is False
    assert row["record"]["nmck_rub"] is None
    f.write_bytes(raw + b"tampered")
    with pytest.raises(ValueError, match="SHA"):
        mod.stage(tmp_path)


def test_quote_and_receipt_identity_rejection(tmp_path, monkeypatch):
    name = "test.bin"
    rel = "captures/commercial_4263966_lot1/" + name
    raw = b"<html><body>some other tender</body></html>"
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    f.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    receipt = {"sha256": sha, "bytes": len(raw), "source_url": mod.URL,
               "case_id": mod.CID, "http_status": 200, "relative_file": rel}
    Path(str(f) + ".json").write_text(json.dumps(receipt))
    monkeypatch.setattr(mod, "ORIGINALS", ((name, sha, mod.URL, ("№ 4263966",)),))
    with pytest.raises(ValueError, match="quote"):
        mod.stage(tmp_path)
    receipt["case_id"] = "commercial:1234567:lot1"
    Path(str(f) + ".json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="identity"):
        mod.stage(tmp_path)
