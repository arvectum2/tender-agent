"""SIBUR first-party original binding; never silently promote a sale."""
import json
from pathlib import Path

import pytest

from scripts.market_intelligence.append_sibur_pq_original import stage
from scripts.market_intelligence.capture_primary_source import store

CID = "commercial:2103585-2:lot1"
ARCHIVE = "https://sibur.ru/ru/procurement/buy/archive/?procedure=2103585%2F2"
FILES = [
    "https://sibur.ru/upload/tmp/example/3f7/dl90o9w6p3wvgqy8ldhc36ik49cm5f0z.7z",
    "https://sibur.ru/upload/tmp/example/f90/3hsr308boy6cevcpvrhnuqdq0e5fota9.7z",
]
QUOTES = ["2103585/2", "Установка компенсации реактивной мощности 10 кВ",
          'ООО "ЗапСибНефтехим"', "Прием предложений завершен"]


def fixture(tmp_path: Path, missing_link=False):
    links = "".join(f'<a href="{u.removeprefix("https://sibur.ru")}">file</a>'
                    for u in FILES[:1 if missing_link else 2])
    html = ("<table><tr><td>2103585/2</td><td>Установка компенсации реактивной мощности 10 кВ"
            '</td><td>ООО "ЗапСибНефтехим"</td><td>Прием предложений завершен</td>'
            f"<td>{links}</td></tr></table>").encode()
    receipts = [store(tmp_path, CID, ARCHIVE, html)]
    receipts += [store(tmp_path, CID, u, b"7z\xbc\xaf\x27\x1c" + bytes([i]) * 100,
                       content_type="application/x-7z-compressed")
                 for i, u in enumerate(FILES, 1)]
    m = {"schema_version": "pq-sibur-primary-incremental/1", "base_db_expected_records": 111,
         "cases": [{"canonical_id": CID, "procedure_id": "2103585/2",
                    "source_receipts": [str(Path(r["receipt_path"]).relative_to(tmp_path))
                                        for r in receipts],
                    "exact_source_quotes": QUOTES, "technical_voltage_kv": 10,
                    "scope": "10kv_compensation_equipment_or_works_unspecified",
                    "market_scope": "10kv_primary_title_only_no_sale",
                    "status": "bids_closed_outcome_unknown",
                    "related_predecessor_procedure": "2103585/1",
                    "project_reference": "PDH2.15383-4015-7.7.6-RFQ-0003",
                    "publication_date": "2025-04-07", "buyer": "ООО «ЗапСибНефтехим»",
                    "description": "10kV PQ request", "signed_supplier_verified": False,
                    "paid_verified": False}]}
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(m, ensure_ascii=False))
    return p, receipts


def test_verified_10kv_source_is_unreviewed_not_sale(tmp_path):
    p, _ = fixture(tmp_path)
    rows, _ = stage(p, tmp_path)
    assert len(rows) == 1
    assert rows[0]["record"]["technical_voltage_kv"] == 10
    assert rows[0]["record"]["paid_verified"] is False
    assert rows[0]["record"]["realized_equipment_revenue_rub"] is None
    assert len(rows[0]["record"]["evidence"]) == 3


def test_source_sha_tamper_rejected(tmp_path):
    p, receipts = fixture(tmp_path)
    original = tmp_path / receipts[1]["relative_file"]
    original.write_bytes(original.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA"):
        stage(p, tmp_path)


def test_unlinked_technical_archive_rejected(tmp_path):
    p, _ = fixture(tmp_path, missing_link=True)
    with pytest.raises(ValueError, match="not linked"):
        stage(p, tmp_path)


def test_invented_signed_supplier_rejected(tmp_path):
    p, _ = fixture(tmp_path)
    m = json.loads(p.read_text())
    m["cases"][0]["signed_supplier_verified"] = True
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="economic outcome"):
        stage(p, tmp_path)
