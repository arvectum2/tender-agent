"""Self-contained regression: 7 DOCX source files are only one procurement."""
import hashlib
import json
import zipfile

import pytest

from scripts.market_intelligence.append_bidzaar_primary_pq import stage, staged_row


def _fixture(tmp_path):
    root = tmp_path
    links = []
    documents = []
    for i in range(7):
        token = f"00000000-0000-0000-0000-{i+1:012d}"
        url = "https://bidzaar.com/api/filestorage/files/download/" + token
        rel = f"spec_{i}.docx"
        path = root / rel
        voltage = "РУ6 кВт." if i == 6 else "Для защиты оборудования 0.4 кВ"
        body = ("Проектирование фильтр гармонических искажений. " + voltage + " ") * 20 + f" Site {i} unique technical annex "
        xml = ("<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
               "<w:body><w:p><w:r><w:t>" + body + "</w:t></w:r></w:p></w:body></w:document>")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as f:
            f.writestr("word/document.xml", xml)
        blob = path.read_bytes()
        documents.append({"url": url, "private_relative": rel,
                          "sha256": hashlib.sha256(blob).hexdigest(),
                          "size_bytes": len(blob)})
        links.append(f'<a href="{url}">Original spec {i}</a>')
    html = (
        "<html><body>281-705 Русагро гармонических искажений "
        "Спецификация по позициям (7) 24.12.2025 14.05.2026"
        + " Genuine first party document representation. " * 24
        + "".join(links) + "</body></html>"
    )
    (root / "card.html").write_text(html, encoding="utf8")
    m = {
        "schema_version": "pq-bidzaar-multisite-originals/1",
        "canonical_id": "commercial:281-705:lot1",
        "source_first_party_url": (
            "https://bidzaar.com/app/process/light/019b4fe0-38ca-773a-91b0-0ff33daedb7d"
        ),
        "source_first_party_html_relative": "card.html",
        "source_first_party_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "lot_count": 1, "positions": 7, "original_docx": documents,
        "equipment_nominal_voltage_kv": None,
        "signed_supplier_verified": False, "named_winner_verified": False,
        "contract_price_verified_rub": None, "equipment_sales_verified_rub": None,
    }
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(m, ensure_ascii=False), encoding="utf8")
    return manifest, m


def test_seven_origins_do_not_expand_legal_lot_count(tmp_path):
    manifest, _ = _fixture(tmp_path)
    m, hashes = stage(manifest, source_root=tmp_path)
    row = staged_row(m, hashes)
    assert len(hashes) == 7
    assert row["cid"] == "commercial:281-705:lot1"
    assert row["record"]["positions"] == 7
    assert row["record"]["lot_count"] == 1
    assert row["record"]["technical"]["nominal_filter_voltage_kv"] is None
    assert row["record"]["supplier_verified"] is False
    assert row["record"]["realized_equipment_revenue_rub"] is None
    assert len(row["metadata"]["source_original_sha256"]) == 8


@pytest.mark.parametrize("patch", [
    {"lot_count": 7},
    {"positions": 1},
    {"equipment_nominal_voltage_kv": 6},
    {"signed_supplier_verified": True},
])
def test_unsupported_claims_refused(tmp_path, patch):
    manifest, m = _fixture(tmp_path)
    m.update(patch)
    manifest.write_text(json.dumps(m), encoding="utf8")
    with pytest.raises(ValueError, match="guard"):
        stage(manifest, source_root=tmp_path)


def test_corrupt_original_rejected(tmp_path):
    manifest, m = _fixture(tmp_path)
    (tmp_path / m["original_docx"][0]["private_relative"]).write_bytes(b"not a DOCX")
    with pytest.raises(ValueError, match="attachment"):
        stage(manifest, source_root=tmp_path)
