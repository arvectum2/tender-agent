"""Regression for source-graded 10 kV compensation EPC case and V37 reporting."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.market_intelligence.render_fgi_full_deck import readable_status, render

ROOT = Path(__file__).resolve().parents[1]
CID = "223fz:32616430382:lot1"
SNAP = ROOT / "data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261101_v37.json"
DELTA = ROOT / "data/market_intelligence/power_quality/source_bound_delta_20261101_poluprovodniki.v1.json"


def test_source_bound_case_never_promotes_first_parts_to_signed_sale():
    manifest = json.loads(DELTA.read_text(encoding="utf8"))
    assert manifest["base_db_expected_records"] == 118
    case = manifest["new_cases"][0]
    rec = case["source_record"]
    assert rec["canonical_id"] == CID
    assert rec["technical"]["compensation_switchgear_voltage_kv"] == 10
    assert rec["technical"]["substation_voltage_kv"] == 220
    assert rec["commission_application_count"] == 2
    assert rec["commission_admitted_count"] == 2
    assert rec["nmck_rub"] == "72183607.13"
    assert rec["contract_registered_price_rub"] is None
    assert rec["signed_supplier_verified"] is False
    assert rec["realized_equipment_revenue_rub"] is None
    assert len({s["sha256"] for s in case["verified_originals"]}) == 5
    assert "Договор указан" not in readable_status(rec["status"], "ru")
    from scripts.market_intelligence.render_pq_client_report import FAMILIES

    assert FAMILIES[rec["family"]] == "Компенсация реактивной мощности"


def test_v37_contains_all_119_lots_and_correct_provisional_status():
    snap = json.loads(SNAP.read_text(encoding="utf8"))
    assert (snap["unique_lots"], snap["distinct_procedures"], snap["eis_223_notices"]) == (119, 108, 42)
    assert len({x["id"] for x in snap["items"]}) == 119
    assert CID in {x["id"] for x in snap["items"]}
    for lang in ("ru", "en"):
        doc, pages = render(snap, lang)
        assert pages == 260
        m = re.search(r'<section[^>]*data-case-id="' + re.escape(CID) + r'".*?</section>', doc, re.DOTALL)
        assert m
        assert "72 183 607" in m.group() or "72,183,607" in m.group()
        assert "Договор указан в источнике" not in m.group()
        assert "Contract reported by source" not in m.group()


def test_v37_pdfs_have_one_case_per_unique_lot():
    pymupdf = pytest.importorskip("pymupdf")
    for lang in ("RU", "EN"):
        p = ROOT / f"docs/market_intelligence/ARVECTUM_FGI_PQ_FULL_{lang}_20261101_V37.pdf"
        with pymupdf.open(p) as doc:
            assert len(doc) == 260
            pages_with_case = sum(CID in page.get_text() for page in doc)
            assert pages_with_case >= 2
