"""v17 archive-origin validation: don't confuse a market survey with awarded PQ sales."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/market_intelligence"
DATA=ROOT/"data/market_intelligence/power_quality"

def load(ver):
    proc=subprocess.run(
        [sys.executable,str(SCRIPTS/f"materialize_pq_research_v{ver}.py")],
        text=True,capture_output=True,timeout=40,check=True,
    )
    return json.loads(proc.stdout)

def test_v17_adds_twelve_unique_archive_records_preserves_87():
    old=load(16)["records"]
    new=load(17)["records"]
    assert len(old)==87
    assert len(new)==99
    assert new[:87]==old
    assert len({r["canonical_id"] for r in new})==99
    assert load(17)["verification_summary"]["new_records_pending_import"]==28

def test_2023_2024_enquiries_no_prices_no_supposed_awards():
    rows=load(17)["records"][87:]
    harampur=[
        r for r in rows if r["demand_group"]=="KHARAMPURNEFTEGAZ-UKRM-MULTI-2023-2024"
    ]
    assert len(harampur)==5
    assert {r["source_event_date"] for r in harampur}=={
        "2023-11-09","2023-12-01","2024-04-11","2024-04-23","2024-05-17"
    }
    assert len({r["canonical_id"] for r in harampur})==5
    assert all(r["nmck_rub"] is None for r in harampur)
    assert all(r["supplier_verified"] is False for r in harampur)
    assert all(r["reported_contract_total_rub"] is None for r in harampur)
    assert all(r["scope"]=="market_sounding" for r in harampur)

def test_2024_service_and_samara_final_only_not_signed_contract():
    rows=load(17)["records"][87:]
    service=next(r for r in rows if "mogocha-statcom" in r["canonical_id"])
    assert service["publication_date"]=="2024-04-15"
    assert service["scope"]=="maintenance"
    assert service["procedure_id"] is None
    samara=next(r for r in rows if "tplus-samara" in r["canonical_id"])
    assert samara["publication_date"] is None
    assert samara["source_event_date"]=="2024-04-27"
    assert samara["reported_final_price_rub"]=="2985440.02"
    assert samara["reported_contract_total_rub"] is None
    assert samara["nmck_rub"] is None
    assert samara["supplier_verified"] is False

def test_2025_sorovskneft_commercial_real_etp_number_and_rospan_index():
    rows=load(17)["records"][87:]
    sorov=next(r for r in rows if r["procedure_id"]=="РН50303773")
    assert sorov["procurement_regime"]=="commercial"
    assert sorov["scope"]=="market_sounding"
    assert sorov["evidence"][0]["url"]=="https://zakupki.kontur.ru/IS50374166"
    rospan=next(r for r in rows if r["publication_date"]=="2025-04-10")
    assert "РОСПАН" in rospan["beneficiary"]
    assert rospan["procedure_id"] is None

def test_source_year_basis_never_forges_unpublished_dates():
    rows=load(17)["records"]
    assert sum(r["publication_date"] is None for r in rows[87:])==1
    for r in rows[87:]:
        assert r["evidence"][0]["url"].startswith("https://")
        assert r["pq_equipment_only_contract_rub"] is None
    years={}
    for r in rows:
        x=r.get("publication_date")
        y=x[:4] if x else "undated"
        years[y]=years.get(y,0)+1
    # two archived UDS records from v12 plus Samara final-date-only listing
    assert years=={"2023":3,"2024":17,"2025":22,"2026":54,"undated":3}
