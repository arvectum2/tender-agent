"""Regression for source-specific, single-lot 223-FZ import without live DB writes."""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.market_intelligence.append_tatneft_lot7 import stage


def fixture(tmp_path):
    url = ("https://www.b2b-center.ru/market/"
           "postavka-elektrotekhnicheskogo-oborudovaniia-vykliuchateli/tender-4469608/")
    notice = (
        "<html><body>32616065155 4469608 199 598 002,40 "
        'ООО "ТН - ЭНЕРГОСБЫТ" Результаты процедуры скрыты '
        + " Original page content. " * 2000 + "</body></html>"
    )
    positions = (
        "<html><body>4469608 Лот №7. Установки конденсаторные "
        "27.12.10.190 на напряжение более 1 кВ 1 компл "
        "3 172 000,00 руб. (сумма с НДС, НДС: 22%) "
        + " original position table. " * 1700 + "</body></html>"
    )
    assert min(len(notice), len(positions)) > 30_000
    (tmp_path / "notice.html").write_text(notice, encoding="utf8")
    (tmp_path / "positions.html").write_text(positions, encoding="utf8")
    case = {
        "schema_version": "pq-tatneft-b2b-lot-primary/1",
        "base_unique_lots": 108,
        "canonical_id": "223fz:32616065155:lot7",
        "eis_notice": "32616065155",
        "b2b_procedure": "4469608",
        "actual_b2b_lot": 7,
        "parent_number_of_positions": 11,
        "customer": "ООО «ТН-Энергосбыт»",
        "organizer": "ПАО «Татнефть»",
        "main_url": url,
        "positions_url": url + "?action=positions",
        "main_original_relative": "notice.html",
        "positions_original_relative": "positions.html",
        "main_html_sha256": hashlib.sha256(notice.encode()).hexdigest(),
        "positions_html_sha256": hashlib.sha256(positions.encode()).hexdigest(),
        "pq_position_limit_rub_gross": "3172000.00",
        "parent_limit_rub_gross": "199598002.40",
        "pq_position_vat_pct": 22,
        "pq_position_units": 1,
        "pq_position_unit": "компл",
        "pq_position_okpd2": "27.12.10.190",
        "equipment_nominal_voltage_kv": None,
        "original_detailed_technical_spec_read": False,
        "winner_verified": False,
        "signed_supplier_verified": False,
        "paid_amount_verified": False,
        "actual_equipment_sale_rub": None,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf8")
    return path, case


def test_primary_evidence_is_exactly_one_unverified_pq_lot(tmp_path):
    path, _ = fixture(tmp_path)
    row, _ = stage(path, source_root=tmp_path)
    record = row["record"]
    assert row["cid"] == "223fz:32616065155:lot7"
    assert record["parent_number_of_lots"] == 11
    assert record["lot_number"] == 7
    assert record["nmck_rub"] == "3172000.00"
    assert record["equipment_nominal_voltage_kv"] is None
    assert record["supplier_verified"] is False
    assert record["realized_equipment_revenue_rub"] is None
    assert len(row["metadata"]["source_original_sha256"]) == 2


@pytest.mark.parametrize("field,value", [
    ("actual_b2b_lot", 1),
    ("parent_number_of_positions", 1),
    ("pq_position_limit_rub_gross", "199598002.40"),
    ("equipment_nominal_voltage_kv", 10),
    ("signed_supplier_verified", True),
])
def test_unsupported_source_promotion_refused(tmp_path, field, value):
    path, case = fixture(tmp_path)
    case[field] = value
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf8")
    with pytest.raises(ValueError, match="guard"):
        stage(path, source_root=tmp_path)


def test_sha_change_refused(tmp_path):
    path, _ = fixture(tmp_path)
    (tmp_path / "positions.html").write_text("tampered", encoding="utf8")
    with pytest.raises(ValueError, match="size|SHA"):
        stage(path, source_root=tmp_path)
